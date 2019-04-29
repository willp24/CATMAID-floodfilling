# -*- coding: utf-8 -*-
import datetime
import subprocess
from pathlib import Path
import json
import pickle

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.db import connection
from django.shortcuts import get_object_or_404

from catmaid.consumers import msg_user
from catmaid.control.authentication import requires_user_role
from catmaid.models import Message, User, UserRole
from catmaid.control.message import notify_user

from celery.task import task

from rest_framework.views import APIView

from autoproofreader.models import (
    AutoproofreaderResult,
    ConfigFile,
    ComputeServer,
    DiluvianModel,
)
from autoproofreader.control.compute_server import GPUUtilAPI


# The path were server side exported files get stored in
output_path = Path(settings.MEDIA_ROOT, settings.MEDIA_EXPORT_SUBDIRECTORY)


class AutoproofreaderTaskAPI(APIView):
    @method_decorator(requires_user_role(UserRole.QueueComputeTask))
    def put(self, request, project_id):
        """
        Flood fill a skeleton.
        Files:
        job_config.json
        volume.toml
        diluvian_config.toml
        skeleton.csv
        """

        files = {f.name: f.read().decode("utf-8") for f in request.FILES.values()}
        for x in [
            "job_config.json",
            "volume.toml",
            "diluvian_config.toml",
            "skeleton.csv",
        ]:
            if x not in files.keys():
                raise Exception(x + " is missing!")

        # pop the job_config since that is needed here, the rest of the files
        # will get passed through to diluvian
        job_config = json.loads(files["job_config.json"])

        # the name of the job, used for storing temporary files
        # and refering to past runs
        job_name = self._get_job_name(job_config)

        # If the temporary directory doesn't exist, create it
        media_folder = Path(settings.MEDIA_ROOT)
        if not (media_folder / job_name).exists():
            (media_folder / job_name).mkdir()
        local_temp_dir = media_folder / job_name

        # Create a copy of the files sent in the request in the
        # temporary directory so that it can be copied with scp
        # in the async function
        for f in files:
            file_path = local_temp_dir / f
            file_path.write_text(files[f])

        # Get the ssh key
        # TODO: determine the most suitable location for ssh keys/paths
        ssh_key_path = settings.SSH_KEY_PATH

        # create a floodfill config object if necessary and pass
        # it to the floodfill results object
        diluvian_config = self._get_diluvian_config(
            request.user.id, project_id, files["diluvian_config.toml"]
        )
        diluvian_config.save()

        # retrieve necessary paths from the chosen server and model
        server = ComputeServer.objects.get(id=job_config["server_id"])
        model = DiluvianModel.objects.get(id=job_config["model_id"])
        server_paths = {
            "address": server.address,
            "working_dir": server.diluvian_path[2:]
            if server.diluvian_path.startswith("~/")
            else server.diluvian_path,
            "results_dir": server.results_directory,
            "env_source": server.environment_source_path,
            "model_file": model.model_source_path,
        }

        # store a job in the database now so that information about
        # ongoing jobs can be retrieved.
        gpus = self._get_gpus(job_config)
        if self._check_gpu_conflict(gpus):
            raise Exception("Not enough compute resources for this job")
        result = AutoproofreaderResult(
            user_id=request.user.id,
            project_id=project_id,
            config_id=diluvian_config.id,
            skeleton_id=job_config["skeleton_id"],
            skeleton_csv=files["skeleton.csv"],
            model_id=job_config["model_id"],
            name=job_name,
            status="queued",
            gpus=gpus,
        )
        result.save()

        msg_user(request.user.id, "autoproofreader-result-update", {"status": "queued"})

        # retrieve the configurations used during the chosen models training.
        # this is used as the base configuration when running since most
        # settings should not be changed or are irrelevant to autoproofreader a
        # skeleton. The settings that do need to be overridden are handled
        # by the config generated by the widget.
        if model.config_id is not None:
            query = ConfigFile.objects.get(id=int(model.config_id))
            model_config = query.config
            file_path = local_temp_dir / "model_config.toml"
            file_path.write_text(model_config)

        if self._check_gpu_conflict():
            raise Exception("Not enough compute resources for this job")

        if job_config.get("segmentation_type", None) is not None:
            # Retrieve segmentation
            x = query_segmentation_async.delay(
                result,
                project_id,
                request.user.id,
                ssh_key_path,
                local_temp_dir,
                server_paths,
                job_name,
                job_config["segmentation_type"],
            )
        else:
            raise ValueError("Segmentation type not available: {}".format(job_config))

        # Send a response to let the user know the async funcion has started
        return JsonResponse({"task_id": x.task_id, "status": "queued"})

    def _get_job_name(self, config):
        """
        Get the name of a job. If the job_name field is not provided generate a default
        job name based on the date and the skeleton id.
        """
        name = config.get("job_name", "")
        if len(name) == 0:
            skid = str(config.get("skeleton_id", None))
            date = str(datetime.datetime.now().date())
            if skid is None:
                raise Exception("missing skeleton id!")
            name = skid + "_" + date

        i = len(AutoproofreaderResult.objects.filter(name__startswith=name))
        if i > 0:
            return "{}_{}".format(name, i)
        else:
            return name

    def _get_gpus(self, config):
        gpus = GPUUtilAPI._query_server(config["server_id"])
        config_gpus = config.get("gpus", [])
        if len(config_gpus) == 0:
            config_gpus = list(range(len(gpus)))
        for g in config_gpus:
            if str(g) not in gpus.keys():
                raise Exception(
                    "There is no gpu with id ({}) on the chosen server".format(g)
                )
        usage = [True if (i in config_gpus) else False for i in range(len(gpus))]
        return usage

    def _check_gpu_conflict(self, gpus=None):
        # returns True if there is a conflict
        ongoing_jobs = AutoproofreaderResult.objects.filter(status="queued")
        if len(ongoing_jobs) == 0:
            # jobs will not have taken compute resources if there
            # are no other jobs. We should probably still check gpu
            # usage stats to see if the gpus are unavailable for some
            # reason other than flood filling jobs.
            return False
        gpu_utils = [job.gpus for job in ongoing_jobs]
        if gpus is not None:
            gpu_utils.append(gpus)

        # There is a conflict if at least one gpu is claimed by at least 2 jobs
        return (
            len(list(filter(lambda x: x > 1, map(lambda *x: sum(x), *gpu_utils)))) > 0
        )

    def _get_diluvian_config(self, user_id, project_id, config):
        """
        get a configuration object for this project. It may make sense to reuse
        configurations accross runs, but that is currently not supported.
        """
        return ConfigFile(user_id=user_id, project_id=project_id, config=config)


@task()
def query_segmentation_async(
    result,
    project_id,
    user_id,
    ssh_key_path,
    local_temp_dir,
    server,
    job_name,
    job_type,
):
    result.status = "computing"
    result.save()
    msg_user(user_id, "autoproofreader-result-update", {"status": "computing"})

    # copy temp files from django local temp media storage to server temp storage
    setup = (
        "scp -i {ssh_key_path} -pr {local_dir} "
        + "{server_address}:{server_results_dir}/{job_dir}"
    ).format(
        **{
            "local_dir": local_temp_dir,
            "server_address": server["address"],
            "server_results_dir": server["results_dir"],
            "job_dir": job_name,
            "ssh_key_path": ssh_key_path,
        }
    )
    files = {}
    for f in local_temp_dir.iterdir():
        files[f.name.split(".")[0]] = Path(
            "~/", server["results_dir"], job_name, f.name
        )

    if job_type == "diluvian":
        extra_parameters = (
            "--model-weights-file {model_file} "
            + "--model-training-config {model_config_file} "
            + "--model-job-config {job_config_file} "
            + "--volume-file {volume_file} "
        ).format(
            **{
                "model_file": server["model_file"],
                "model_config_file": files["model_config"],
                "job_config_file": files["diluvian_config"],
                "volume_file": files["volume"],
            }
        )
    elif job_type == "watershed":
        extra_parameters = ""

    # connect to the server and run the autoproofreader algorithm on the provided skeleton
    query_seg = (
        "ssh -i {ssh_key_path} {server}\n"
        + "source {server_ff_env_path}\n"
        + "sarbor-error-detector "
        + "--skeleton-csv {skeleton_file} "
        + "--sarbor-config {sarbor_config} "
        + "--output-file {output_file} "
        + "{segmentation_type} "
        + "{type_parameters}"
    ).format(
        **{
            "ssh_key_path": ssh_key_path,
            "server": server["address"],
            "server_ff_env_path": server["env_source"],
            "skeleton_file": files["skeleton"],
            "sarbor_config": files["sarbor_config"],
            "output_file": Path(server["results_dir"], job_name, job_name),
            "segmentation_type": job_type,
            "type_parameters": extra_parameters,
        }
    )

    # Copy the numpy file containing the volume mesh and the csv containing the node connections
    # predicted by the autoproofreader run.

    #    "rm -r {server_working_dir}/{server_results_dir}/{server_job_dir}\n"
    cleanup = (
        "scp -i {ssh_key_path} -r {server}:"
        + "{server_results_dir}/{server_job_dir}/* {local_temp_dir}\n"
    ).format(
        **{
            "ssh_key_path": ssh_key_path,
            "server": server["address"],
            "server_results_dir": server["results_dir"],
            "server_job_dir": job_name,
            "output_file_name": job_name + "_output",
            "local_temp_dir": local_temp_dir,
        }
    )

    process = subprocess.Popen(
        "/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf8"
    )
    out, err = process.communicate(setup)
    print(out)

    process = subprocess.Popen(
        "/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf8"
    )
    out, err = process.communicate(query_seg)
    print(out)

    process = subprocess.Popen(
        "/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding="utf8"
    )
    out, err = process.communicate(cleanup)
    print(out)

    new_nodes = pickle.load(
        open("{}/{}/{}".format(local_temp_dir, job_name, "nodes.obj"), "rb")
    )

    # overwrite input skeleton csv
    # This should probably be fixed to have input/output skeleton csvs
    result.skeleton_csv = "\n".join(
        [",".join([str(c) for c in row]) for row in new_nodes]
    )

    msg = Message()
    msg.user = User.objects.get(pk=int(user_id))
    msg.read = False

    msg.title = "Job {} complete!"
    msg.text = "IM DOING SOME STUFF, CHECK IT OUT"
    msg.action = "localhost:8000"

    notify_user(user_id, msg.id, msg.title)

    result.completion_time = datetime.datetime.now()
    with open("{}/{}/{}.csv".format(local_temp_dir, job_name, "rankings")) as f:
        result.data = f.read()
    result.status = "complete"
    result.save()

    msg_user(user_id, "autoproofreader-result-update", {"status": "completed"})

    return "complete"


class AutoproofreaderResultAPI(APIView):
    @method_decorator(requires_user_role(UserRole.Browse))
    def get(self, request, project_id):
        """
        List all available autoproofreader models
        ---
        parameters:
          - name: project_id
            description: Project of the returned configurations
            type: integer
            paramType: path
            required: true
          - name: model_id
            description: If available, return only the model associated with model_id
            type: int
            paramType: form
            required: false
            defaultValue: false
        """
        if request.query_params.get("uuid", request.data.get("uuid", False)):
            return self.get_uuid(request, project_id)

        result_id = request.query_params.get(
            "result_id", request.data.get("result_id", None)
        )
        result = self.get_results(result_id)

        return JsonResponse(
            result, safe=False, json_dumps_params={"sort_keys": True, "indent": 4}
        )

    @method_decorator(requires_user_role(UserRole.Browse))
    def get_uuid(self, request, project_id):
        result_id = request.query_params.get(
            "result_id", request.data.get("result_id", None)
        )
        result = get_object_or_404(AutoproofreaderResult, id=result_id)

        return JsonResponse(
            result.uuid, safe=False, json_dumps_params={"sort_keys": True, "indent": 4}
        )

    @method_decorator(requires_user_role(UserRole.QueueComputeTask))
    def delete(self, request, project_id):
        # can_edit_or_fail(request.user, point_id, "point")
        result_id = request.query_params.get(
            "result_id", request.data.get("result_id", None)
        )
        if result_id is not None:
            result = get_object_or_404(AutoproofreaderResult, id=result_id)
            result.delete()
            return JsonResponse({"success": True})
        return JsonResponse({"success": False})

    def get_results(self, result_id=None):
        cursor = connection.cursor()
        if result_id is not None:
            cursor.execute(
                """
                SELECT * FROM autoproofreader_autoproofreaderresult
                WHERE id = {}
                """.format(
                    result_id
                )
            )
        else:
            cursor.execute(
                """
                SELECT * FROM autoproofreader_autoproofreaderresult
                """
            )
        desc = cursor.description
        return [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]

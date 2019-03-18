from django.http import JsonResponse
from django.db import connection
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator

from catmaid.control.authentication import requires_user_role
from catmaid.models import UserRole
from floodfilling.models import VolumeConfig
from rest_framework.views import APIView


class VolumeConfigAPI(APIView):
    @method_decorator(requires_user_role(UserRole.QueueComputeTask))
    def put(self, request, project_id):
        warnings = []

        name = request.POST.get("name", None)
        config = request.POST.get("config", None)

        params = [name, config]

        if any([x is None for x in params]):
            return JsonResponse({"success": False, "results": request.POST})

        volume_config = VolumeConfig(name=name, config=config)
        volume_config.save()

        return JsonResponse({"success": True, "warnings": warnings})

    @method_decorator(requires_user_role(UserRole.Browse))
    def get(self, request, project_id):
        """
        List all available volume configurations
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
        returns: List of lists of the form:
            [
                id,
                user_id,
                project_id,
                creation_time,
                edition_time,
                name,
                config,
            ]
        """
        volume_config_id = request.query_params.get("volume_config_id", None)
        result = self.get_volume_configs(volume_config_id)

        return JsonResponse(
            result, safe=False, json_dumps_params={"sort_keys": True, "indent": 4}
        )

    @method_decorator(requires_user_role(UserRole.QueueComputeTask))
    def delete(self, request, project_id):
        # can_edit_or_fail(request.user, point_id, "point")
        volume_config_id = request.query_params.get("volume_config_id", None)

        model = get_object_or_404(VolumeConfig, id=volume_config_id)
        model.delete()

        return JsonResponse({"success": True})

    def get_volume_configs(self, model_id=None):
        cursor = connection.cursor()
        if model_id is not None:
            cursor.execute(
                """
                SELECT * FROM volume_config
                WHERE id = {}
                """.format(
                    model_id
                )
            )
        else:
            cursor.execute(
                """
                SELECT * FROM volume_config
                """
            )
        desc = cursor.description
        return [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]

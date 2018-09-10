# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2017-10-18 18:26

from django.conf import settings
from django.db import migrations, models
from django.contrib.postgres.fields import ArrayField
import django.db.models.deletion
import django.utils.timezone

forward_create_tables = """
    CREATE TABLE floodfill_config (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        config text
    );

    CREATE TABLE floodfill_model (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        name text,
        server_id int REFERENCES compute_server(id) ON DELETE CASCADE NOT NULL,
        environment_source_path text,
        diluvian_path text,
        results_directory text,
        model_source_path text,
        config_id int REFERENCES floodfill_config(id) ON DELETE CASCADE NOT NULL
    );

    CREATE TABLE floodfill_results (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        completion_time timestamptz,
        name text,
        data text,
        status text CHECK (status IN ('queued', 'computing', 'complete', 'error')),
        config int REFERENCES floodfill_config(id),
        model int REFERENCES floodfill_model(id),
        volume int REFERENCES catmaid_volume(id),
        skeleton_id int,
        skeleton_csv text
    );

    -- Create history tables
    SELECT create_history_table('floodfill_config'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('floodfill_model'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('floodfill_results'::regclass, 'edition_time', 'txid');
"""

backward_create_tables = """
    SELECT drop_history_table('floodfill_config'::regclass);
    SELECT drop_history_table('floodfill_model'::regclass);
    SELECT drop_history_table('floodfill_results'::regclass);

    DROP TABLE floodfill_config CASCADE;
    DROP TABLE floodfill_model CASCADE;
    DROP TABLE floodfill_results CASCADE;
"""


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("floodfilling", "0001_create_compute_server_table"),
    ]

    operations = [
        migrations.RunSQL(
            forward_create_tables,
            backward_create_tables,
            [
                migrations.CreateModel(
                    name="FloodfillConfig",
                    fields=[
                        (
                            "id",
                            models.AutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "creation_time",
                            models.DateTimeField(default=django.utils.timezone.now),
                        ),
                        (
                            "edition_time",
                            models.DateTimeField(default=django.utils.timezone.now),
                        ),
                        ("config", models.TextField()),
                    ],
                    options={"db_table": "floodfill_config"},
                ),
                migrations.CreateModel(
                    name="FloodfillModel",
                    fields=[
                        (
                            "id",
                            models.AutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "creation_time",
                            models.DateTimeField(default=django.utils.timezone.now),
                        ),
                        (
                            "edition_time",
                            models.DateTimeField(default=django.utils.timezone.now),
                        ),
                        ("name", models.TextField()),
                        ("status", models.TextField()),
                        ("data", models.TextField()),
                    ],
                    options={"db_table": "floodfill_config"},
                ),
                migrations.CreateModel(
                    name="FloodfillResults",
                    fields=[
                        (
                            "id",
                            models.AutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "creation_time",
                            models.DateTimeField(default=django.utils.timezone.now),
                        ),
                        (
                            "edition_time",
                            models.DateTimeField(default=django.utils.timezone.now),
                        ),
                        ("name", models.TextField()),
                        ("skeleton_csv", models.TextField()),
                        ("environment_source_path", models.TextField()),
                        ("diluvian_path", models.TextField()),
                        ("results_directory", models.TextField()),
                        ("model_source_path", models.TextField()),
                        (
                            "skeleton",
                            models.ForeignKey(
                                to="catmaid.ClassInstance", on_delete=models.CASCADE
                            ),
                        ),
                    ],
                    options={"db_table": "floodfill_config"},
                ),
            ],
        )
    ]

"""Tests for settings models."""

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.settings import OMEROInstance, Settings


class TestOMEROInstance:
    def test_with_defaults(self):
        inst = OMEROInstance(host="omero.example.com", username="admin")
        assert inst.name is None
        assert inst.port == 4064

    def test_full(self):
        inst = OMEROInstance(
            name="Production OMERO",
            host="omero.example.com",
            port=4065,
            username="admin",
        )
        assert inst.name == "Production OMERO"
        assert inst.port == 4065


class TestSettings:
    def test_full_construction(self):
        s = Settings(
            deployment_mode="desktop",
            output_data_folder="/data/output",
            external_editor="code {file_path}",
        )
        assert s.deployment_mode == "desktop"
        assert s.output_data_folder == "/data/output"
        assert s.external_editor == "code {file_path}"

    def test_defaults(self):
        s = Settings(deployment_mode="webapp", output_data_folder="/out")
        assert s.external_editor is None
        assert s.napari_env_path is None
        assert s.omero_instances == []
        assert s.tool_store_path == "~/.bioimageflow/tool_packages/"
        assert s.update_mode == "auto"
        assert s.execution_engine == "sequential"
        assert s.cache_max_executions is None
        assert s.cache_max_age is None
        assert s.keyboard_shortcuts == {}
        assert s.dev_mode is True

    def test_invalid_deployment_mode(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="cloud", output_data_folder="/out")

    def test_invalid_execution_engine(self):
        with pytest.raises(ValidationError):
            Settings(
                deployment_mode="desktop",
                output_data_folder="/out",
                execution_engine="spark",
            )

    def test_with_omero_instances(self):
        s = Settings(
            deployment_mode="desktop",
            output_data_folder="/out",
            omero_instances=[
                OMEROInstance(host="omero1.example.com", username="user1"),
                OMEROInstance(host="omero2.example.com", username="user2"),
            ],
        )
        assert len(s.omero_instances) == 2
        assert s.omero_instances[0].host == "omero1.example.com"

    def test_json_roundtrip(self):
        s = Settings(
            deployment_mode="desktop",
            output_data_folder="/out",
            keyboard_shortcuts={"Ctrl+S": "save", "Ctrl+Z": "undo"},
            omero_instances=[
                OMEROInstance(host="omero.example.com", username="admin"),
            ],
        )
        rebuilt = Settings.model_validate_json(s.model_dump_json())
        assert rebuilt.keyboard_shortcuts == s.keyboard_shortcuts
        assert rebuilt.omero_instances[0].host == "omero.example.com"

    def test_update_mode_accepts_auto(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/out", update_mode="auto")
        assert s.update_mode == "auto"

    def test_update_mode_accepts_manual(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/out", update_mode="manual")
        assert s.update_mode == "manual"

    def test_update_mode_accepts_version_string(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/out", update_mode="1.5.0")
        assert s.update_mode == "1.5.0"

    def test_datasets_root_defaults_to_none(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/out")
        assert s.datasets_root is None

    def test_datasets_root_accepts_explicit_path(self):
        s = Settings(
            deployment_mode="desktop",
            output_data_folder="/out",
            datasets_root="/data/datasets",
        )
        assert s.datasets_root == "/data/datasets"

    def test_max_upload_size_default(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/out")
        assert s.max_upload_size == 2 * 1024**3

    def test_max_upload_size_override(self):
        s = Settings(
            deployment_mode="desktop", output_data_folder="/out", max_upload_size=500_000
        )
        assert s.max_upload_size == 500_000

    def test_resolved_datasets_root_uses_output_folder_by_default(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/data/output")
        assert s.resolved_datasets_root() == "/data/output/datasets"

    def test_resolved_datasets_root_honors_explicit_value(self):
        s = Settings(
            deployment_mode="desktop",
            output_data_folder="/data/output",
            datasets_root="/elsewhere/datasets",
        )
        assert s.resolved_datasets_root() == "/elsewhere/datasets"

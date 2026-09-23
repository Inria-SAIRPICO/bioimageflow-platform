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

    def test_trims_metadata_and_empty_name_becomes_none(self):
        inst = OMEROInstance(
            name="  ",
            host="  omero.example.com  ",
            username="  admin  ",
        )
        assert inst.name is None
        assert inst.host == "omero.example.com"
        assert inst.username == "admin"

    @pytest.mark.parametrize("field", ["host", "username"])
    def test_requires_non_empty_host_and_username(self, field: str):
        payload = {"host": "omero.example.com", "username": "admin"}
        payload[field] = "  "
        with pytest.raises(ValidationError):
            OMEROInstance.model_validate(payload)

    @pytest.mark.parametrize("port", [0, 65536])
    def test_rejects_invalid_tcp_ports(self, port: int):
        with pytest.raises(ValidationError):
            OMEROInstance(host="omero.example.com", username="admin", port=port)


class TestSettings:
    def test_full_construction(self):
        s = Settings(
            deployment_mode="desktop",
            external_editor="code {file_path}",
        )
        assert s.deployment_mode == "desktop"
        assert s.external_editor == "code {file_path}"

    def test_defaults(self):
        s = Settings(deployment_mode="webapp")
        assert s.external_editor is None
        assert s.omero_instances == []
        assert s.tool_store_path == "~/.bioimageflow/tool_packages/"
        assert s.update_mode == "auto"
        assert s.new_workflow_execution == "sequential"
        assert s.default_execution_target_id == "local"
        assert s.node_data_page_size == 250
        assert s.keyboard_shortcuts == {}
        assert s.dev_mode is True
        assert s.enable_unsafe_webapp_features is False

    def test_unsafe_webapp_features_flag(self):
        s = Settings(deployment_mode="webapp", enable_unsafe_webapp_features=True)
        assert s.enable_unsafe_webapp_features is True

    def test_legacy_output_data_folder_is_rejected(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", output_data_folder="/tmp/x")

    def test_latest_output_materialization_is_not_user_configurable(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", latest_output_mode="copy")

    def test_invalid_deployment_mode(self):
        with pytest.raises(ValidationError):
            Settings.model_validate({"deployment_mode": "cloud"})

    def test_invalid_new_workflow_execution(self):
        with pytest.raises(ValidationError):
            Settings.model_validate(
                {
                    "deployment_mode": "desktop",
                    "new_workflow_execution": "spark",
                }
            )

    def test_new_workflow_execution_dask_rejected(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", new_workflow_execution="dask")

    @pytest.mark.campaign_excluded(reason="parallel-scheduling")
    def test_new_workflow_execution_parallel_is_valid(self):
        s = Settings(deployment_mode="desktop", new_workflow_execution="parallel")
        assert s.new_workflow_execution == "parallel"

    def test_old_execution_engine_is_not_a_live_field(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", execution_engine="parallel")

    def test_with_omero_instances(self):
        s = Settings(
            deployment_mode="desktop",
            omero_instances=[
                OMEROInstance(host="omero1.example.com", username="user1"),
                OMEROInstance(host="omero2.example.com", username="user2"),
            ],
        )
        assert len(s.omero_instances) == 2
        assert s.omero_instances[0].host == "omero1.example.com"

    def test_omero_effective_names_must_be_unique(self):
        with pytest.raises(ValidationError):
            Settings(
                deployment_mode="desktop",
                omero_instances=[
                    OMEROInstance(name="prod", host="omero1.example.com", username="a"),
                    OMEROInstance(name=" prod ", host="omero2.example.com", username="b"),
                ],
            )

    def test_omero_default_display_names_must_be_unique(self):
        with pytest.raises(ValidationError):
            Settings(
                deployment_mode="desktop",
                omero_instances=[
                    OMEROInstance(host="omero.example.com", username="admin"),
                    OMEROInstance(host="omero.example.com", port=4065, username="admin"),
                ],
            )

    def test_omero_password_is_not_a_persisted_model_field(self):
        with pytest.raises(ValidationError):
            Settings.model_validate(
                {
                    "deployment_mode": "desktop",
                    "omero_instances": [
                        {
                            "host": "omero.example.com",
                            "username": "admin",
                            "password": "secret",
                        }
                    ],
                }
            )

    def test_json_roundtrip(self):
        s = Settings(
            deployment_mode="desktop",
            keyboard_shortcuts={"Ctrl+S": "save", "Ctrl+Z": "undo"},
            omero_instances=[
                OMEROInstance(host="omero.example.com", username="admin"),
            ],
        )
        rebuilt = Settings.model_validate_json(s.model_dump_json())
        assert rebuilt.keyboard_shortcuts == s.keyboard_shortcuts
        assert rebuilt.omero_instances[0].host == "omero.example.com"

    def test_json_roundtrip_preserves_none_defaults(self):
        s = Settings(deployment_mode="desktop", external_editor=None)
        dumped = s.model_dump()
        assert dumped["external_editor"] is None
        rebuilt = Settings.model_validate_json(s.model_dump_json())
        assert rebuilt.external_editor is None

    def test_update_mode_accepts_auto(self):
        s = Settings(deployment_mode="desktop", update_mode="auto")
        assert s.update_mode == "auto"

    def test_update_mode_accepts_manual(self):
        s = Settings(deployment_mode="desktop", update_mode="manual")
        assert s.update_mode == "manual"

    def test_update_mode_accepts_version_string(self):
        s = Settings(deployment_mode="desktop", update_mode="1.5.0")
        assert s.update_mode == "1.5.0"

    def test_datasets_root_defaults_to_none(self):
        s = Settings(deployment_mode="desktop")
        assert s.datasets_root is None

    def test_datasets_root_accepts_explicit_path(self):
        s = Settings(
            deployment_mode="desktop",
            datasets_root="/data/datasets",
        )
        assert s.datasets_root == "/data/datasets"

    def test_max_upload_size_default(self):
        s = Settings(deployment_mode="desktop")
        assert s.max_upload_size == 2 * 1024**3

    def test_max_upload_size_override(self):
        s = Settings(deployment_mode="desktop", max_upload_size=500_000)
        assert s.max_upload_size == 500_000

    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            Settings.model_validate({"deployment_mode": "desktop", "foo": 1})

    def test_dev_mode_false_accepted_at_model_layer(self):
        # Router rejects this in GUI mode; the model itself stays permissive
        # so non-GUI callers (CLI, tests, future webapp deployments) can build
        # Settings(dev_mode=False).
        s = Settings(deployment_mode="desktop", dev_mode=False)
        assert s.dev_mode is False

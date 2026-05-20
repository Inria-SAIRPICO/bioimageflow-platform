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
            output_data_folder="/data/output",
            external_editor="code {file_path}",
        )
        assert s.deployment_mode == "desktop"
        assert s.output_data_folder == "/data/output"
        assert s.external_editor == "code {file_path}"

    def test_defaults(self):
        # Settings(deployment_mode=...) should be constructible without
        # an explicit output_data_folder thanks to default_factory.
        s = Settings(deployment_mode="webapp")
        assert s.external_editor is None
        assert s.napari_env_path is None
        assert s.omero_instances == []
        assert s.output_data_folder == "~/bioimageflow_data/"
        assert s.tool_store_path == "~/.bioimageflow/tool_packages/"
        assert s.update_mode == "auto"
        assert s.execution_engine == "sequential"
        assert s.cache_max_executions is None
        assert s.cache_max_age is None
        assert s.keyboard_shortcuts == {}
        assert s.dev_mode is True
        assert s.enable_unsafe_webapp_features is False

    def test_unsafe_webapp_features_flag(self):
        s = Settings(deployment_mode="webapp", enable_unsafe_webapp_features=True)
        assert s.enable_unsafe_webapp_features is True

    def test_output_data_folder_overridable(self):
        s = Settings(deployment_mode="desktop", output_data_folder="/tmp/x")
        assert s.output_data_folder == "/tmp/x"

    def test_invalid_deployment_mode(self):
        with pytest.raises(ValidationError):
            Settings.model_validate({"deployment_mode": "cloud", "output_data_folder": "/out"})

    def test_invalid_execution_engine(self):
        with pytest.raises(ValidationError):
            Settings.model_validate(
                {
                    "deployment_mode": "desktop",
                    "output_data_folder": "/out",
                    "execution_engine": "spark",
                }
            )

    def test_execution_engine_dask_rejected(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", execution_engine="dask")

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
            output_data_folder="/out",
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
        s = Settings(deployment_mode="desktop", output_data_folder="/out", max_upload_size=500_000)
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

    # --- Validators added by the Settings Panel plan, Task 1 ---

    def test_cache_max_executions_zero_is_valid(self):
        s = Settings(deployment_mode="desktop", cache_max_executions=0)
        assert s.cache_max_executions == 0

    def test_cache_max_executions_positive_is_valid(self):
        s = Settings(deployment_mode="desktop", cache_max_executions=5)
        assert s.cache_max_executions == 5

    def test_cache_max_executions_none_is_valid(self):
        s = Settings(deployment_mode="desktop", cache_max_executions=None)
        assert s.cache_max_executions is None

    def test_cache_max_executions_negative_rejected(self):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", cache_max_executions=-1)

    @pytest.mark.parametrize("value", ["30d", "1h", "45m", "10s", "999d"])
    def test_cache_max_age_accepts_valid_strings(self, value: str):
        s = Settings(deployment_mode="desktop", cache_max_age=value)
        assert s.cache_max_age == value

    @pytest.mark.parametrize("value", ["1 day", "30D", "abc", "", "10x", "d10"])
    def test_cache_max_age_rejects_invalid_strings(self, value: str):
        with pytest.raises(ValidationError):
            Settings(deployment_mode="desktop", cache_max_age=value)

    def test_cache_max_age_none_is_valid(self):
        s = Settings(deployment_mode="desktop", cache_max_age=None)
        assert s.cache_max_age is None

    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            Settings.model_validate({"deployment_mode": "desktop", "foo": 1})

    def test_dev_mode_false_accepted_at_model_layer(self):
        # Router rejects this in GUI mode; the model itself stays permissive
        # so non-GUI callers (CLI, tests, future webapp deployments) can build
        # Settings(dev_mode=False).
        s = Settings(deployment_mode="desktop", dev_mode=False)
        assert s.dev_mode is False

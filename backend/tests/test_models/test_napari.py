"""Tests for napari Pydantic models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.napari import NapariOpenRequest, NapariStatus


class TestNapariOpenRequest:
    def test_with_paths_and_clear_layers_true(self):
        req = NapariOpenRequest(paths=["/tmp/a.tif", "/tmp/b.tif"], clear_layers=True)
        assert req.paths == ["/tmp/a.tif", "/tmp/b.tif"]
        assert req.clear_layers is True

    def test_default_clear_layers_false(self):
        req = NapariOpenRequest(paths=["/tmp/a.tif"])
        assert req.clear_layers is False

    def test_empty_paths_list_is_valid(self):
        req = NapariOpenRequest(paths=[])
        assert req.paths == []

    def test_missing_paths_raises_validation_error(self):
        with pytest.raises(ValidationError):
            NapariOpenRequest()  # type: ignore[call-arg]

    def test_environment_reader_fields_and_reader_normalization(self):
        environment_id = uuid4()
        request = NapariOpenRequest(
            paths=["/tmp/a.tif"],
            environment_id=environment_id,
            reader_id="  org.example.reader  ",
        )
        assert request.environment_id == environment_id
        assert request.reader_id == "org.example.reader"
        assert NapariOpenRequest(paths=[], reader_id="  ").reader_id is None


class TestNapariStatus:
    def test_full_construction(self):
        s = NapariStatus(running=True, env_path="/envs/napari", pid=4242)
        assert s.running is True
        assert s.env_path == "/envs/napari"
        assert s.pid == 4242

    def test_defaults(self):
        s = NapariStatus(running=False)
        assert s.env_path is None
        assert s.pid is None

    def test_json_round_trip(self):
        s = NapariStatus(running=True, env_path="/envs/napari", pid=4242)
        data = s.model_dump_json()
        restored = NapariStatus.model_validate_json(data)
        assert restored == s

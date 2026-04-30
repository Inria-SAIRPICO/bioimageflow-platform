"""Tests for OMERO credential keyring adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bioimageflow_server.models.settings import OMEROInstance
from bioimageflow_server.services.omero_credentials import (
    KeyringOmeroCredentialStore,
    OmeroCredentialError,
    OmeroCredentialKey,
)


def test_key_uses_specified_service_and_username() -> None:
    key = OmeroCredentialKey.from_instance(
        OMEROInstance(host="omero.example.com", port=4065, username="admin")
    )
    assert key.service == "bioimageflow-omero"
    assert key.username == "omero.example.com:4065:admin"


def test_adapter_delegates_get_set_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, str, str | None]] = []

    def get_password(service: str, username: str) -> str | None:
        calls.append(("get", service, username, None))
        return "secret"

    def set_password(service: str, username: str, password: str) -> None:
        calls.append(("set", service, username, password))

    def delete_password(service: str, username: str) -> None:
        calls.append(("delete", service, username, None))

    fake_keyring = SimpleNamespace(
        get_password=get_password,
        set_password=set_password,
        delete_password=delete_password,
        errors=SimpleNamespace(PasswordDeleteError=RuntimeError),
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.omero_credentials._import_keyring",
        lambda: fake_keyring,
    )

    store = KeyringOmeroCredentialStore()
    key = OmeroCredentialKey("bioimageflow-omero", "host:4064:user")
    assert store.get_password(key) == "secret"
    store.set_password(key, "new-secret")
    store.delete_password(key)

    assert calls == [
        ("get", "bioimageflow-omero", "host:4064:user", None),
        ("set", "bioimageflow-omero", "host:4064:user", "new-secret"),
        ("delete", "bioimageflow-omero", "host:4064:user", None),
    ]


def test_delete_missing_password_is_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class PasswordDeleteError(Exception):
        pass

    def delete_password(service: str, username: str) -> None:
        raise PasswordDeleteError("not found")

    fake_keyring = SimpleNamespace(
        delete_password=delete_password,
        errors=SimpleNamespace(PasswordDeleteError=PasswordDeleteError),
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.omero_credentials._import_keyring",
        lambda: fake_keyring,
    )

    KeyringOmeroCredentialStore().delete_password(
        OmeroCredentialKey("bioimageflow-omero", "host:4064:user")
    )


def test_set_failure_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def set_password(service: str, username: str, password: str) -> None:
        raise RuntimeError("backend unavailable")

    fake_keyring = SimpleNamespace(set_password=set_password, errors=SimpleNamespace())
    monkeypatch.setattr(
        "bioimageflow_server.services.omero_credentials._import_keyring",
        lambda: fake_keyring,
    )

    with pytest.raises(OmeroCredentialError):
        KeyringOmeroCredentialStore().set_password(
            OmeroCredentialKey("bioimageflow-omero", "host:4064:user"), "secret"
        )

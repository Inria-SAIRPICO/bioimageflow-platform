"""OMERO credential storage adapter.

OMERO passwords are intentionally kept out of settings JSON. This module owns
the small keyring boundary used by the settings store and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bioimageflow_server.models.settings import OMEROInstance


OMERO_KEYRING_SERVICE = "bioimageflow-omero"


class OmeroCredentialError(RuntimeError):
    """Raised when the configured keyring backend cannot complete an operation."""


@dataclass(frozen=True)
class OmeroCredentialKey:
    """Keyring service/username pair for one OMERO credential."""

    service: str
    username: str

    @classmethod
    def from_instance(cls, instance: OMEROInstance) -> "OmeroCredentialKey":
        return cls(
            service=OMERO_KEYRING_SERVICE,
            username=f"{instance.host}:{instance.port}:{instance.username}",
        )


class OmeroCredentialStore(Protocol):
    """Minimal injectable credential store used by SettingsStore."""

    def get_password(self, key: OmeroCredentialKey) -> str | None: ...

    def set_password(self, key: OmeroCredentialKey, password: str) -> None: ...

    def delete_password(self, key: OmeroCredentialKey) -> None: ...


def _import_keyring():
    try:
        import keyring
    except Exception as exc:  # noqa: BLE001
        raise OmeroCredentialError("Python keyring is not available") from exc
    return keyring


class KeyringOmeroCredentialStore:
    """OMERO credential adapter backed by Python ``keyring``."""

    def get_password(self, key: OmeroCredentialKey) -> str | None:
        keyring = _import_keyring()
        try:
            return keyring.get_password(key.service, key.username)
        except Exception as exc:  # noqa: BLE001
            raise OmeroCredentialError("Could not read OMERO password state") from exc

    def set_password(self, key: OmeroCredentialKey, password: str) -> None:
        keyring = _import_keyring()
        try:
            keyring.set_password(key.service, key.username, password)
        except Exception as exc:  # noqa: BLE001
            raise OmeroCredentialError("Could not store OMERO password") from exc

    def delete_password(self, key: OmeroCredentialKey) -> None:
        keyring = _import_keyring()
        password_delete_error = getattr(
            getattr(keyring, "errors", object()), "PasswordDeleteError", ()
        )
        try:
            keyring.delete_password(key.service, key.username)
        except password_delete_error:
            return
        except Exception as exc:  # noqa: BLE001
            raise OmeroCredentialError("Could not delete OMERO password") from exc

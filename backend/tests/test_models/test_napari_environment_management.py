"""Strict managed napari recipe and operation API contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.napari_environments import (
    NapariEnvironmentOperation,
    NapariManagedEnvironmentCopy,
    NapariManagedEnvironmentCreate,
    NapariManagedRecipe,
    NapariManagedRecipeSelection,
)


def test_default_and_legacy_recipes_resolve_to_supported_matrix() -> None:
    default = NapariManagedRecipeSelection().resolved()
    legacy = NapariManagedRecipeSelection(preset="legacy").resolved()

    assert default == NapariManagedRecipe(
        source="managed",
        preset="default",
        python="==3.12.*",
        napari="0.9.1",
        qt="PyQt6",
        requested_packages=[],
        channels=["conda-forge"],
    )
    assert legacy.napari == "0.6.6"
    assert legacy.qt == "PyQt5"
    assert legacy.python == "==3.12.*"


def test_advanced_recipe_requires_exact_napari_and_qt() -> None:
    with pytest.raises(ValidationError, match="exact napari version and Qt choice"):
        NapariManagedRecipeSelection(preset="advanced")
    with pytest.raises(ValidationError, match="exact valid version"):
        NapariManagedRecipeSelection(preset="advanced", napari=">=0.9", qt="PyQt6")
    with pytest.raises(ValidationError, match="select only Python 3.12"):
        NapariManagedRecipeSelection(
            preset="advanced", python=">=3.12", napari="0.9.2", qt="PyQt6"
        )

    recipe = NapariManagedRecipeSelection(
        preset="advanced", napari="0.9.2", qt="PyQt6"
    ).resolved()
    assert recipe.napari == "0.9.2"
    assert recipe.qt == "PyQt6"


@pytest.mark.parametrize(
    "requirement, message",
    [
        ("napari>=0.9", "controlled by the managed recipe"),
        ("PyQt6", "controlled by the managed recipe"),
        ("plugin @ https://example.test/plugin.whl", "resolve from PyPI"),
        ("plugin>=1; python_version >= '3.12'", "do not support environment markers"),
        ("not a req !!!", "invalid requested PyPI requirement"),
    ],
)
def test_requested_plugins_reject_reserved_or_non_pypi_requirements(
    requirement: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        NapariManagedRecipeSelection(requested_packages=[requirement])


def test_requested_plugins_are_normalized_and_deduplicated() -> None:
    selection = NapariManagedRecipeSelection(
        requested_packages=["Example_Plugin[reader]>=1"]
    )
    assert selection.requested_packages == ["Example_Plugin[reader]>=1"]
    with pytest.raises(ValidationError, match="duplicate requested distribution"):
        NapariManagedRecipeSelection(requested_packages=["example_plugin", "example-plugin>=1"])


def test_create_copy_and_operation_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NapariManagedEnvironmentCreate(
            name="Viewer", expected_revision=0, install_command="pip install napari"
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NapariManagedEnvironmentCopy(
            name="Copy", expected_revision=0, source_path="/tmp/environment"
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NapariEnvironmentOperation(
            id=uuid4(),
            environment_id=uuid4(),
            kind="create",
            state="pending",
            progress=0,
            message="Queued",
            command=["pip", "install"],
        )

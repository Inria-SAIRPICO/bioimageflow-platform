"""Tests for the thumbnail_generator helper script's pure logic.

The helper lives under ``_external/`` and is launched as a subprocess
inside the thumbnail Wetlands env (which has ``bioio`` + ``pillow``
installed). For unit tests we load it via ``importlib.util`` and stub
``bioio`` so the test process never imports it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock


def _make_bioio_stub(captured: dict[str, Any] | None = None) -> ModuleType:
    """Stub ``bioio`` so module-level imports succeed in tests."""
    mod = ModuleType("bioio")
    captured = captured if captured is not None else {}

    class _FakeBioImage:
        def __init__(self, path: Any) -> None:
            captured["path"] = str(path)

        def get_image_data(self, order: str) -> Any:
            captured["order"] = order
            return captured.get("data")

    mod.__dict__["BioImage"] = _FakeBioImage
    return mod


def _load_module(bioio_stub: ModuleType | None = None) -> ModuleType:
    backend_root = Path(__file__).resolve().parents[2]
    script_path = (
        backend_root
        / "src"
        / "bioimageflow_server"
        / "_external"
        / "thumbnail_generator.py"
    )
    if bioio_stub is None:
        bioio_stub = _make_bioio_stub()
    sys.modules["bioio"] = bioio_stub
    spec = importlib.util.spec_from_file_location("thumbnail_generator", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# create_thumbnail (eager) — runs in pool worker
# ---------------------------------------------------------------------------


def test_create_thumbnail_writes_png_for_2d_array(tmp_path: Path) -> None:
    import numpy as np
    captured: dict[str, Any] = {"data": np.zeros((1, 1, 1, 64, 32), dtype=np.uint8)}
    captured["data"][0, 0, 0, :, :] = np.linspace(0, 255, 64 * 32, dtype=np.uint8).reshape(64, 32)
    bioio_stub = _make_bioio_stub(captured)

    tg = _load_module(bioio_stub)

    image_path = tmp_path / "image.tif"
    image_path.write_bytes(b"fake-tiff-content")  # bioio is stubbed; bytes don't matter
    thumbnail_path = tmp_path / "thumbs" / "image.png"

    tg.create_thumbnail(str(image_path), "tif", str(thumbnail_path), size=(32, 32))

    assert thumbnail_path.is_file()
    assert thumbnail_path.read_bytes().startswith(b"\x89PNG")
    # The TCZYX order request reaches bioio, with the canonical-extension symlink
    assert captured["order"] == "TCZYX"


def test_create_thumbnail_passes_string_path_to_bioimage(tmp_path: Path) -> None:
    import numpy as np

    captured: dict[str, Any] = {"data": np.zeros((1, 1, 1, 8, 8), dtype=np.uint8)}

    class _StrictBioImage:
        def __init__(self, path: Any) -> None:
            if not isinstance(path, str):
                raise TypeError(f"expected str path, got {type(path)}")
            captured["path"] = path

        def get_image_data(self, order: str) -> Any:
            captured["order"] = order
            return captured["data"]

    bioio_stub = ModuleType("bioio")
    bioio_stub.__dict__["BioImage"] = _StrictBioImage
    tg = _load_module(bioio_stub)

    image_path = tmp_path / "image.tif"
    image_path.write_bytes(b"x")
    thumbnail_path = tmp_path / "thumb.png"

    tg.create_thumbnail(str(image_path), "tif", str(thumbnail_path), size=(8, 8))

    assert captured["path"] == str(image_path)
    assert thumbnail_path.is_file()


def test_create_thumbnail_handles_constant_image(tmp_path: Path) -> None:
    """All-zero image must not crash on division by zero — should still write a PNG."""
    import numpy as np
    captured: dict[str, Any] = {"data": np.zeros((1, 1, 1, 16, 16), dtype=np.uint8)}
    bioio_stub = _make_bioio_stub(captured)

    tg = _load_module(bioio_stub)

    image_path = tmp_path / "flat.tif"
    image_path.write_bytes(b"x")
    thumbnail_path = tmp_path / "flat.png"

    tg.create_thumbnail(str(image_path), "tif", str(thumbnail_path), size=(16, 16))

    assert thumbnail_path.is_file()
    assert thumbnail_path.read_bytes().startswith(b"\x89PNG")


def test_create_thumbnail_creates_canonical_extension_symlink(tmp_path: Path) -> None:
    """Mirrors Galaxy's behaviour: bioio is invoked on a path that ends with
    ``.{extension}`` (a symlink to the actual file when the extensions
    differ). The symlink is cleaned up after generation."""
    import numpy as np
    captured: dict[str, Any] = {"data": np.zeros((1, 1, 1, 8, 8), dtype=np.uint8)}
    bioio_stub = _make_bioio_stub(captured)

    tg = _load_module(bioio_stub)

    # Real file has no extension; we ask the generator to add ".tif".
    image_path = tmp_path / "datasetfile_no_extension"
    image_path.write_bytes(b"fake")
    thumbnail_path = tmp_path / "out.png"

    tg.create_thumbnail(str(image_path), "tif", str(thumbnail_path), size=(8, 8))

    bioio_called_with = captured["path"]
    assert bioio_called_with.endswith(".tif"), bioio_called_with
    # Symlink must be cleaned up afterwards.
    assert not Path(bioio_called_with).exists() or bioio_called_with == str(image_path)


def test_create_thumbnail_handles_rgba_data(tmp_path: Path) -> None:
    import numpy as np
    rgba = np.zeros((1, 4, 1, 16, 16), dtype=np.uint8)
    rgba[0, 0] = 255  # red channel saturated
    captured: dict[str, Any] = {"data": rgba}
    bioio_stub = _make_bioio_stub(captured)

    tg = _load_module(bioio_stub)
    image_path = tmp_path / "img.tif"
    image_path.write_bytes(b"x")
    thumbnail_path = tmp_path / "rgba.png"

    tg.create_thumbnail(str(image_path), "tif", str(thumbnail_path), size=(16, 16))

    assert thumbnail_path.is_file()


# ---------------------------------------------------------------------------
# queue_generate_thumbnail (fire-and-forget)
# ---------------------------------------------------------------------------


def test_queue_generate_thumbnail_submits_to_pool(tmp_path: Path) -> None:
    """Should call ``apply_async`` on a multiprocessing.Pool and return None."""
    tg = _load_module()
    # Reset module-level pool so this test is independent
    tg._pool = None

    fake_pool = mock.MagicMock()
    with mock.patch.object(tg.multiprocessing, "Pool", return_value=fake_pool) as pool_ctor:
        result = tg.queue_generate_thumbnail(
            str(tmp_path / "in.tif"), "tif", str(tmp_path / "out.png"), size=(64, 64)
        )

    assert result is None
    pool_ctor.assert_called_once()
    fake_pool.apply_async.assert_called_once()
    args, kwargs = fake_pool.apply_async.call_args
    # First positional: the create_thumbnail callable
    assert args[0] is tg.create_thumbnail
    # Second positional: the args tuple passed to create_thumbnail
    submitted_args = args[1]
    assert submitted_args == (
        str(tmp_path / "in.tif"),
        "tif",
        str(tmp_path / "out.png"),
        (64, 64),
    )
    # error_callback wired so a failed task logs instead of silently dropping
    assert "error_callback" in kwargs
    assert callable(kwargs["error_callback"])


def test_queue_generate_thumbnail_reuses_pool(tmp_path: Path) -> None:
    """A second call must not spin up a new Pool — Galaxy's behaviour."""
    tg = _load_module()
    tg._pool = None

    fake_pool = mock.MagicMock()
    with mock.patch.object(tg.multiprocessing, "Pool", return_value=fake_pool) as pool_ctor:
        tg.queue_generate_thumbnail(str(tmp_path / "a"), "tif", str(tmp_path / "a.png"))
        tg.queue_generate_thumbnail(str(tmp_path / "b"), "tif", str(tmp_path / "b.png"))

    assert pool_ctor.call_count == 1
    assert fake_pool.apply_async.call_count == 2


def test_on_error_does_not_raise() -> None:
    """The error_callback must swallow and log — never propagate to the pool."""
    tg = _load_module()
    try:
        tg._on_error(RuntimeError("boom"))
    except Exception as exc:  # pragma: no cover - defensive
        raise AssertionError(f"_on_error should not raise: {exc!r}")

"""Tests for the thumbnail_generator helper script's pure logic.

The helper lives under ``_external/`` and is called by a Wetlands worker
inside the thumbnail environment. For unit tests we load it via
``importlib.util`` and stub
``bioio`` plus its TIFF reader so the test process never imports them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


def _make_bioio_stub(captured: dict[str, Any] | None = None) -> ModuleType:
    """Stub ``bioio`` so module-level imports succeed in tests."""
    mod = ModuleType("bioio")
    captured = captured if captured is not None else {}

    class _FakeBioImage:
        def __init__(self, path: Any, reader: Any = None) -> None:
            captured["path"] = str(path)
            captured["reader"] = reader
            self.dims = SimpleNamespace(T=captured["data"].shape[0], Z=captured["data"].shape[2])

        def get_image_dask_data(self, order: str, **selectors: int) -> Any:
            captured["order"] = order
            captured["selectors"] = selectors

            def compute():
                captured["computed"] = True
                data = captured["data"][selectors["T"], :, selectors["Z"], ...]
                if data.ndim == 3:
                    data = data[..., None]
                return data.transpose(1, 2, 0, 3)

            return SimpleNamespace(compute=compute)

    mod.__dict__["BioImage"] = _FakeBioImage
    return mod


def _load_module(
    bioio_stub: ModuleType | None = None,
    tifffile_stub: ModuleType | None = None,
) -> ModuleType:
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
    if tifffile_stub is None:
        tifffile_stub = ModuleType("bioio_tifffile")
        tifffile_stub.__dict__["Reader"] = type("TiffReader", (), {})
    sys.modules["bioio"] = bioio_stub
    sys.modules["bioio_tifffile"] = tifffile_stub
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
    assert captured["order"] == "YXCS"
    assert captured["selectors"] == {"T": 0, "Z": 0}
    assert captured["reader"].__name__ == "TiffReader"


def test_thumbnail_publication_is_atomic(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
    from PIL import Image

    source = tmp_path / "source.tif"
    source.write_bytes(b"tiff")
    destination = tmp_path / "thumbnail.png"
    helper = _load_module(_make_bioio_stub({"data": np.zeros((1, 1, 1, 8, 8))}))
    original_save = Image.Image.save

    def save(image, path, *args, **kwargs):
        assert Path(path) != destination
        assert not destination.exists()
        original_save(image, path, *args, **kwargs)
        assert not destination.exists()

    monkeypatch.setattr(Image.Image, "save", save)
    helper.create_thumbnail(str(source), "tif", str(destination))
    assert destination.read_bytes().startswith(b"\x89PNG")
    assert list(tmp_path.glob("*.png")) == [destination]


def test_create_thumbnail_passes_string_path_to_bioimage(tmp_path: Path) -> None:
    import numpy as np

    captured: dict[str, Any] = {"data": np.zeros((1, 1, 1, 8, 8), dtype=np.uint8)}

    class _StrictBioImage(_make_bioio_stub(captured).BioImage):
        def __init__(self, path: Any, reader: Any = None) -> None:
            if not isinstance(path, str):
                raise TypeError(f"expected str path, got {type(path)}")
            super().__init__(path, reader)

    bioio_stub = ModuleType("bioio")
    bioio_stub.__dict__["BioImage"] = _StrictBioImage
    tg = _load_module(bioio_stub)

    image_path = tmp_path / "image.tif"
    image_path.write_bytes(b"x")
    thumbnail_path = tmp_path / "thumb.png"

    tg.create_thumbnail(str(image_path), "tif", str(thumbnail_path), size=(8, 8))

    assert captured["path"] == str(image_path)
    assert captured["reader"].__name__ == "TiffReader"
    assert thumbnail_path.is_file()


def test_create_thumbnail_uses_bioio_discovery_for_non_tiff(tmp_path: Path) -> None:
    import numpy as np

    captured: dict[str, Any] = {"data": np.zeros((1, 1, 1, 8, 8), dtype=np.uint8)}
    bioio_stub = _make_bioio_stub(captured)
    tg = _load_module(bioio_stub)

    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"fake-png-content")
    thumbnail_path = tmp_path / "thumb.png"

    tg.create_thumbnail(str(image_path), "png", str(thumbnail_path), size=(8, 8))

    assert captured["path"] == str(image_path)
    assert captured["reader"] is None
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


def test_preview_selects_middle_plane_lazily_and_preserves_rgb_samples(tmp_path: Path) -> None:
    import numpy as np
    from PIL import Image

    # T,C,Z,Y,X,S: unused planes deliberately differ from the chosen plane.
    data = np.full((3, 1, 5, 8, 8, 3), 100, dtype=np.uint8)
    data[1, 0, 2] = [255, 0, 0]
    captured = {"data": data}
    helper = _load_module(_make_bioio_stub(captured))
    source = tmp_path / "rgb.png"
    source.write_bytes(b"image")
    destination = tmp_path / "preview.png"

    helper.create_thumbnail(str(source), "png", str(destination))

    assert captured["selectors"] == {"T": 1, "Z": 2}
    assert captured["computed"] is True
    assert captured["reader"] is None
    with Image.open(destination) as preview:
        assert preview.mode == "RGB"
        assert preview.getpixel((0, 0)) == (255, 0, 0)

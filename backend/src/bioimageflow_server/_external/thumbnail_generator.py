# Self-contained script — do NOT add imports from bioimageflow_server.
# Executed inside the thumbnail Wetlands env (which provides bioio +
# pillow + numpy + the bioio readers). The manager (services/
# thumbnail_manager.py) calls this module's ``queue_generate_thumbnail``
# via ``env.execute(...)``; it returns immediately after submitting to
# an in-env multiprocessing.Pool, so each manager call is fire-and-
# forget.
"""Thumbnail generator helper (subprocess-side).

Pattern lifted from Galaxy's ``galaxy/thumbnail_generator.py``: a
single-process pool dispatches per-image renders so the Wetlands worker
can return its IPC response immediately and accept the next request.
"""

from __future__ import annotations

import multiprocessing
import traceback
from pathlib import Path
from typing import Any

_pool: Any = None

if __name__ == "__main__":  # pragma: no cover
    multiprocessing.set_start_method("spawn")


def create_thumbnail(
    image_path: str,
    extension: str,
    thumbnail_path: str,
    size: tuple[int, int] = (128, 128),
) -> None:
    """Render a thumbnail for ``image_path`` and write a PNG to
    ``thumbnail_path``.

    Runs in a pool worker — heavy imports (bioio, numpy, PIL) are kept
    lazy here so the manager-side test loader doesn't need them.
    """
    import numpy as np
    from PIL import Image
    from bioio import BioImage

    # Galaxy fallback: bioio dispatches readers by file extension. When
    # the dataset on disk doesn't end with the canonical extension
    # (e.g. Galaxy's ``dataset_NNN.dat``), we point bioio at a temporary
    # symlink that does. Cleaned up in the finally block.
    image_path_with_extension = Path(image_path).with_suffix(f".{extension}")
    created_symlink = False
    try:
        if not image_path_with_extension.exists():
            image_path_with_extension.symlink_to(image_path)
            created_symlink = True

        if image_path_with_extension.suffix.lower() in {".tif", ".tiff"}:
            # This endpoint always renders one concrete file, never a TIFF glob.
            # Select the single-file reader explicitly so numeric filename
            # components cannot make bioio-tiff-glob claim the image as a series.
            from bioio_tifffile import Reader as TiffReader

            image = BioImage(str(image_path_with_extension), reader=TiffReader)
        else:
            image = BioImage(str(image_path_with_extension))
        data = image.get_image_data("TCZYX")
    finally:
        if created_symlink and image_path_with_extension.exists():
            image_path_with_extension.unlink()

    # Pick the middle T and Z slice; keep all channels.
    data = data[data.shape[0] // 2, :, data.shape[2] // 2, :, :]
    # Reorder to YXC for PIL.
    data = data.transpose(1, 2, 0)

    data = data.astype(np.float32)
    data_min = float(data.min())
    data_max = float(data.max())

    if data_max == data_min:
        data_normalized = np.zeros_like(data, dtype=np.uint8)
    else:
        data_normalized = (data - data_min) / (data_max - data_min) * 255.0
        data_normalized = data_normalized.astype(np.uint8)

    channels = data_normalized.shape[2]
    if channels >= 4:
        img = Image.fromarray(data_normalized[..., :4], "RGBA")
    elif channels == 3:
        img = Image.fromarray(data_normalized[..., :3], "RGB")
    elif channels == 2:
        img = Image.fromarray(data_normalized[..., :2], "LA")
    else:
        img = Image.fromarray(data_normalized.squeeze(axis=2), "L")

    img.thumbnail(size)
    Path(thumbnail_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(thumbnail_path)


def _on_error(exc: BaseException) -> None:
    """Pool error_callback — logs and never raises (would kill the pool)."""
    try:
        print("[ERROR] thumbnail_generator worker failed:")
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    except Exception:  # pragma: no cover - defensive
        pass


def queue_generate_thumbnail(
    image_path: str,
    extension: str,
    thumbnail_path: str,
    size: tuple[int, int] = (128, 128),
) -> None:
    """Submit one render task to the in-env pool. Returns immediately.

    The pool is created lazily on first call and reused — Galaxy's
    convention. Eight workers is a generous upper bound; the bioio +
    bioformats stack is I/O bound so over-subscribing helps.
    """
    global _pool
    if _pool is None:
        _pool = multiprocessing.Pool(8)
    _pool.apply_async(
        create_thumbnail,
        (image_path, extension, thumbnail_path, size),
        error_callback=_on_error,
    )

"""Image thumbnail generation and cache."""

from __future__ import annotations

import hashlib
import os
from io import BytesIO
from pathlib import Path


class ThumbnailService:
    """Generate square PNG thumbnails for image paths."""

    _SUPPORTED_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
    # TODO(nifti): platform_specs_v1.md lists NIfTI thumbnails; implement
    # nibabel-backed support or amend the spec before adding .nii/.nii.gz here.

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail(self, file_path: str | Path, size: int = 128) -> bytes:
        path = Path(file_path)
        if not path.is_file() or not self._is_supported(path):
            return self._placeholder_png(size)

        cache_path = self.cache_dir / f"{self._cache_key(path, size)}.png"
        if cache_path.is_file():
            return cache_path.read_bytes()

        try:
            png_bytes = self._render_thumbnail(path, size)
        except Exception:  # noqa: BLE001 - thumbnails must not break the table
            return self._placeholder_png(size)

        cache_path.write_bytes(png_bytes)
        return png_bytes

    def _cache_key(self, path: Path, size: int) -> str:
        absolute = str(path.resolve())
        mtime = str(os.path.getmtime(path))
        return hashlib.sha256(f"{absolute}{mtime}{size}".encode("utf-8")).hexdigest()

    def _is_supported(self, path: Path) -> bool:
        suffixes = [s.lower() for s in path.suffixes]
        if suffixes[-2:] == [".nii", ".gz"]:
            return False
        return path.suffix.lower() in self._SUPPORTED_EXTENSIONS

    def _render_thumbnail(self, path: Path, size: int) -> bytes:
        from PIL import Image

        if path.suffix.lower() in {".tif", ".tiff"}:
            import tifffile

            arr = tifffile.imread(path)
            arr = self._project_array(arr)
            if arr.ndim == 2:
                arr = self._scale_to_uint8(arr)
                image = Image.fromarray(arr, mode="L")
            else:
                arr = self._scale_to_uint8(arr)
                image = Image.fromarray(arr[..., :3])
        else:
            image = Image.open(path)

        image = image.convert("RGBA")
        image.thumbnail((size, size))
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        offset = ((size - image.width) // 2, (size - image.height) // 2)
        canvas.paste(image, offset)

        buf = BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _project_array(arr):
        import numpy as np

        arr = np.asarray(arr)
        if arr.ndim <= 2:
            return arr
        if arr.ndim == 3 and arr.shape[-1] in (3, 4):
            return arr
        while arr.ndim > 3:
            arr = arr[0]
        if arr.ndim == 3 and arr.shape[-1] not in (3, 4):
            arr = arr.max(axis=0)
        return arr

    @staticmethod
    def _scale_to_uint8(arr):
        import numpy as np

        arr = np.asarray(arr)
        if arr.dtype == np.uint8:
            return arr
        arr = arr.astype("float32")
        finite = np.isfinite(arr)
        if not finite.any():
            return np.zeros(arr.shape, dtype="uint8")
        lo = float(arr[finite].min())
        hi = float(arr[finite].max())
        if hi <= lo:
            return np.zeros(arr.shape, dtype="uint8")
        return ((arr - lo) / (hi - lo) * 255).clip(0, 255).astype("uint8")

    @staticmethod
    def _placeholder_png(size: int) -> bytes:
        try:
            from PIL import Image, ImageDraw

            image = Image.new("RGBA", (size, size), (245, 245, 245, 255))
            draw = ImageDraw.Draw(image)
            draw.line((size * 0.25, size * 0.25, size * 0.75, size * 0.75), fill=(150, 150, 150, 255), width=max(1, size // 16))
            draw.line((size * 0.75, size * 0.25, size * 0.25, size * 0.75), fill=(150, 150, 150, 255), width=max(1, size // 16))
            buf = BytesIO()
            image.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            # 1x1 transparent PNG.
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

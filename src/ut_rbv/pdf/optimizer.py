"""Image and PDF stream compression optimizer."""

import io
import logging
from pathlib import Path
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)


class PDFOptimizer:
    """Handles image compression and PDF file size reduction."""

    COMPRESSION_QUALITY = {
        "none": 100,
        "medium": 85,
        "high": 70,
    }

    @classmethod
    def optimize_image_bytes(
        cls,
        img_bytes: bytes,
        compress_level: str = "medium",
    ) -> bytes:
        """Compress raw JPEG/PNG image bytes according to selected compression level."""
        quality = cls.COMPRESSION_QUALITY.get(compress_level.lower(), 85)
        if quality >= 100:
            return img_bytes

        try:
            with Image.open(io.BytesIO(img_bytes)) as img:
                # Convert RGBA to RGB for JPEG optimization
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality, optimize=True)
                optimized_bytes = buffer.getvalue()

                # Only return optimized if smaller than original
                if len(optimized_bytes) < len(img_bytes):
                    return optimized_bytes
                return img_bytes
        except Exception as e:
            logger.debug(f"Gagal mengompres citra: {e}")
            return img_bytes

    @classmethod
    def optimize_image_file(
        cls,
        input_path: Path,
        output_path: Optional[Path] = None,
        compress_level: str = "medium",
    ) -> Path:
        """Optimize and overwrite or save image file with controlled compression."""
        target_path = output_path or input_path
        quality = cls.COMPRESSION_QUALITY.get(compress_level.lower(), 85)
        if quality >= 100:
            return target_path

        try:
            with Image.open(input_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(target_path, format="JPEG", quality=quality, optimize=True)
                return target_path
        except Exception as e:
            logger.debug(f"Gagal mengompres berkas citra {input_path}: {e}")
            return input_path

import io
from pathlib import Path
from typing import Tuple

from PIL import Image, UnidentifiedImageError


def _has_alpha(mode: str) -> bool:
    return mode in {"LA", "RGBA", "PA"} or "A" in mode


def _processed_key(original_key: str, extension: str) -> str:
    stem = Path(original_key).stem
    parent = Path(original_key).parent
    filename = f"{stem}.processed.{extension}"
    return str(parent / filename)


def process_image_bytes(
    data: bytes,
    *,
    target_width: int = 585,
) -> Tuple[bytes, str, str]:
    """Process image according to ingest rules and return bytes, content type, processed key suffix."""
    try:
        image = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise ValueError("Object is not a valid image") from exc

    # Convert to LAB when possible, otherwise grayscale
    try:
        lab = image.convert("LAB")
        l_channel = lab.getchannel("L")
    except Exception:
        l_channel = image.convert("L")

    # Duplicate L channel to 3 channels
    processed_image = Image.merge("RGB", (l_channel, l_channel, l_channel))

    # Resize to target width, preserving aspect ratio
    width, height = processed_image.size
    if width <= 0 or height <= 0:
        raise ValueError("Image has invalid dimensions")
    if width != target_width:
        new_height = max(1, round(height * target_width / width))
        processed_image = processed_image.resize((target_width, new_height), Image.LANCZOS)

    # Decide format
    fmt = "PNG" if _has_alpha(image.mode) else "JPEG"
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"

    buffer = io.BytesIO()
    save_kwargs = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = 90
        save_kwargs["optimize"] = True
    processed_image.save(buffer, **save_kwargs)
    buffer.seek(0)
    return buffer.read(), content_type, fmt.lower()


def build_processed_key(original_key: str, extension: str) -> str:
    return _processed_key(original_key, extension)

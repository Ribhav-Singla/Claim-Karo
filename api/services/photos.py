"""Uploaded photos on disk, served by the API at /static/photos/<id>.jpg.

The agent grades a photo from memory; this keeps the bytes so the browser can show the
thumbnail again when the user comes back to continue the claim.
"""

from __future__ import annotations

from pathlib import Path

PHOTO_DIR = Path(__file__).resolve().parent.parent / "static" / "photos"
URL_PREFIX = "/static/photos"


def save(photo_id: str, image: bytes) -> str:
    """Write the photo and return its URL path (relative to the API origin)."""
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    (PHOTO_DIR / f"{photo_id}.jpg").write_bytes(image)
    return url(photo_id)


def url(photo_id: str) -> str:
    return f"{URL_PREFIX}/{photo_id}.jpg"


def exists(photo_id: str) -> bool:
    return (PHOTO_DIR / f"{photo_id}.jpg").is_file()

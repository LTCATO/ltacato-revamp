"""
Upload files to Supabase Storage and return public URLs.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from typing import BinaryIO

from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "ltcato-media")
ALLOWED_IMAGE = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
ALLOWED_VIDEO = frozenset({".mp4", ".webm", ".mov"})
ALLOWED_DOC = frozenset({".pdf"})

_bucket_ready = False


def _safe_name(filename: str) -> str:
    base = re.sub(r"[^\w.\-]+", "-", (filename or "file").strip().lower())
    return base[:120] or "file"


def _ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename[filename.rfind(".") :].lower()


def _content_type_for_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    if ext == ".mp4":
        return "video/mp4"
    if ext == ".webm":
        return "video/webm"
    if ext == ".mov":
        return "video/quicktime"
    if ext == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def ensure_bucket() -> None:
    """Create the storage bucket if it does not already exist.

    Uses the service-role key so this only runs on the server side.
    Silently succeeds if the bucket already exists.
    """
    global _bucket_ready
    if _bucket_ready:
        return
    try:
        client = get_supabase()
        # Try to create the bucket as public so uploaded files have public URLs.
        client.storage.create_bucket(BUCKET, options={"public": True})
        logger.info("Storage bucket '%s' created.", BUCKET)
    except Exception as exc:
        # "already exists" is not a real error – just mark it ready.
        msg = str(exc).lower()
        if "already exists" in msg or "duplicate" in msg or "409" in msg:
            pass  # bucket already there, that's fine
        else:
            logger.warning("Could not create storage bucket '%s': %s", BUCKET, exc)
    # Either it exists already or we just created it – either way, proceed.
    _bucket_ready = True


# Maximum allowed file sizes
_MAX_IMAGE = 10 * 1024 * 1024  # 10 MB
_MAX_VIDEO = 50 * 1024 * 1024  # 50 MB
_MAX_DOC = 10 * 1024 * 1024  # 10 MB


def upload_file(
    file_obj: BinaryIO,
    filename: str,
    *,
    folder: str = "events",
    content_type: str | None = None,
) -> str:
    ensure_bucket()

    ext = _ext(filename)
    path = f"{folder}/{uuid.uuid4().hex}_{_safe_name(filename)}"
    data = file_obj.read()
    if not data:
        raise ValueError("Empty file")

    # Enforce per-type size limits
    if ext in ALLOWED_IMAGE and len(data) > _MAX_IMAGE:
        raise ValueError(f"Image too large (max 10 MB): {filename}")
    if ext in ALLOWED_VIDEO and len(data) > _MAX_VIDEO:
        raise ValueError(f"Video too large (max 50 MB): {filename}")
    if ext in ALLOWED_DOC and len(data) > _MAX_DOC:
        raise ValueError(f"Document too large (max 10 MB): {filename}")

    ct = content_type or _content_type_for_ext(ext)
    client = get_supabase()

    # Retry once on transient socket / connection errors (e.g. WinError 10035)
    for attempt in range(2):
        try:
            client.storage.from_(BUCKET).upload(
                path, data, file_options={"content-type": ct}
            )  # type: ignore[arg-type]
            break
        except Exception as exc:
            msg = str(exc).lower()
            if attempt == 0 and (
                "10035" in msg
                or "would block" in msg
                or "timeout" in msg
                or "connection" in msg
            ):
                logger.warning(
                    "Upload attempt 1 failed (%s), retrying in 1 s: %s", filename, exc
                )
                time.sleep(1)
                continue
            raise

    return client.storage.from_(BUCKET).get_public_url(path)


def upload_image(file_obj: BinaryIO, filename: str, *, folder: str = "events") -> str:
    ext = _ext(filename)
    if ext not in ALLOWED_IMAGE:
        raise ValueError(f"Unsupported image type: {ext or 'unknown'}")
    return upload_file(file_obj, filename, folder=folder)


def upload_optional_file(
    file_storage,
    *,
    folder: str,
    kind: str = "image",
) -> str | None:
    """Upload a file and return its public URL, or None if no file / upload fails."""
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    name = file_storage.filename
    if not name or not str(name).strip():
        return None
    ext = _ext(name)
    try:
        if kind == "image" and ext not in ALLOWED_IMAGE:
            raise ValueError(f"Invalid image: {name}")
        if kind == "video" and ext not in ALLOWED_VIDEO:
            raise ValueError(f"Invalid video: {name}")
        if kind == "document" and ext not in ALLOWED_DOC:
            raise ValueError(f"Invalid document: {name}")
        return upload_file(file_storage.stream, name, folder=folder)
    except Exception as exc:
        logger.warning("File upload skipped (%s): %s", name, exc)
        return None


def upload_gallery_files(file_list, *, folder: str = "events/gallery") -> list[str]:
    urls: list[str] = []
    for f in file_list or []:
        if not f or not getattr(f, "filename", None) or not str(f.filename).strip():
            continue
        try:
            url = upload_image(f.stream, f.filename, folder=folder)
            urls.append(url)
        except Exception as exc:
            logger.warning("Gallery upload skipped (%s): %s", f.filename, exc)
    return urls

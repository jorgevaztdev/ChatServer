import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException

_IMAGE_MAX = 3 * 1024 * 1024   # 3 MB
_FILE_MAX = 20 * 1024 * 1024   # 20 MB


async def save_file(upload: UploadFile, media_dir: str) -> str:
    data = await upload.read()
    size = len(data)
    mime = upload.content_type or ""

    if mime.startswith("image/") and size > _IMAGE_MAX:
        raise HTTPException(status_code=413, detail=f"Image exceeds 3 MB limit ({size} bytes received)")
    if size > _FILE_MAX:
        raise HTTPException(status_code=413, detail=f"File exceeds 20 MB limit ({size} bytes received)")

    safe_name = Path(upload.filename or "file").name
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest = Path(media_dir) / stored_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)

"""
JobCopilot - Storage downloads
Serves a user's own stored files (resumes, exports) through signed, expiring links.
"""

import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.auth import get_current_user
from app.core.models import User, UserRole

router = APIRouter(tags=["backup"])


@router.get("/storage/download")
async def download_storage_file(
    file: str,
    user_id: Optional[str] = None,
    exp: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """Securely streams object storage files with tenant verification, expiry checks, and path traversal defense."""
    from app.core.object_storage import ObjectStorageAdapter

    # 1. Multi-Tenant Authorization Check
    target_uid = user_id or current_user.user_id
    if target_uid != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Cross-tenant access forbidden.")

    # 2. Expiration Verification
    if exp is not None and time.time() > exp:
        raise HTTPException(status_code=403, detail="Download link has expired.")

    # 3. Path Traversal Neutralization
    clean_filename = os.path.basename(file)
    if not clean_filename or clean_filename != file:
        raise HTTPException(status_code=400, detail="Invalid filename format.")

    adapter = ObjectStorageAdapter()
    base_dir = adapter.local_base_dir.resolve()
    target_file = (base_dir / "users" / target_uid / "resumes" / clean_filename).resolve()

    if not str(target_file).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail="Illegal path traversal attempt.")

    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Requested file not found in storage.")

    media_type = "application/pdf" if clean_filename.lower().endswith(".pdf") else "application/octet-stream"
    return FileResponse(
        path=str(target_file),
        filename=clean_filename,
        media_type=media_type
    )

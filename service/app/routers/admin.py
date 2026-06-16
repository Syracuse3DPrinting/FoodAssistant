"""Admin utilities: backup download, system status."""
import io
import zipfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/backup")
async def download_backup():
    """Stream a zip of all FoodAssistant app data as a browser download.

    Includes settings.json, the SQLite database, and any user-edited data
    files (staples.txt, etc.). Does NOT include Grocy or Mealie data since
    those live in separate containers — back those up with their own tools
    or use the host-level scripts/backup.sh.
    """
    data_dir = Path(settings.data_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if data_dir.exists():
            for f in sorted(data_dir.rglob("*")):
                if f.is_file():
                    arc_name = Path("foodassistant-data") / f.relative_to(data_dir)
                    zf.write(f, arc_name)
    buf.seek(0)
    filename = f"foodassistant-backup-{date.today()}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

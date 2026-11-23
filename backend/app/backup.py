"""Create a consistent SQLite backup without stopping the API."""
from datetime import date
from pathlib import Path
import sqlite3
from sqlalchemy.engine import make_url
from app.core.config import settings


def backup() -> Path:
    url = make_url(settings.database_url)
    if url.drivername != "sqlite" or not url.database:
        raise RuntimeError("La copia de seguridad integrada solo admite SQLite")
    destination_dir = Path(url.database).parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"holos-{date.today().isoformat()}.db"
    source = sqlite3.connect(url.database)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


if __name__ == "__main__":
    print(backup())

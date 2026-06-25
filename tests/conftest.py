import sys
from pathlib import Path

import pytest

# Make `app` importable the same way the container does (workdir /app == service/)
sys.path.insert(0, str(Path(__file__).parent.parent / "service"))

# Make the Stream Deck controller package importable for its pure-logic tests.
sys.path.insert(0, str(Path(__file__).parent.parent / "streamdeck"))

# Create the app's tables on its own engine up front. A few tests exercise the
# real SessionLocal (not an in-memory override), and on a clean database (CI,
# or a fresh checkout) those tables would not exist yet. create_all is
# idempotent, so this is a no-op when the tables already exist.
from app.database import engine, Base  # noqa: E402
from app.models import db_models  # noqa: E402,F401 - registers models with Base

Base.metadata.create_all(bind=engine)


@pytest.fixture
def anyio_backend():
    """Run @pytest.mark.anyio async tests on asyncio only (no trio dependency)."""
    return "asyncio"

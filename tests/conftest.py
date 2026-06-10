import sys
from pathlib import Path

# Make `app` importable the same way the container does (workdir /app == service/)
sys.path.insert(0, str(Path(__file__).parent.parent / "service"))

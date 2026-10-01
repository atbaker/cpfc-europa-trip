"""Generate the frontend contract without opening a database or Temporal connection."""

import json
from pathlib import Path

from cpfc_trip.api import create_app

Path(".data").mkdir(exist_ok=True)
Path(".data/openapi.json").write_text(json.dumps(create_app().openapi(), indent=2) + "\n")

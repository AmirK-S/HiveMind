"""Export OpenAPI spec from the HiveMind FastAPI app to a static JSON file.

This script imports the FastAPI app directly (no server required) and extracts
the OpenAPI spec, writing it to openapi.json at the project root.

Usage:
    python scripts/export_openapi.py

The generated openapi.json is a build artifact — do NOT commit it to version control.
It is consumed by `make generate-sdks` and then discarded.
"""

import json
import sys
from pathlib import Path

# Ensure the project root is on the Python path so hivemind imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hivemind.server.main import app  # noqa: E402

spec = app.openapi()

output_path = project_root / "openapi.json"
with open(output_path, "w") as f:
    json.dump(spec, f, indent=2)

print(f"OpenAPI spec exported to {output_path}")
print(f"Paths: {list(spec.get('paths', {}).keys())}")

#!/usr/bin/env python3
"""
scripts/export-openapi.py

Exports the FastAPI OpenAPI spec to contracts/openapi.json (plan Part 8:
"OpenAPI spec generated and exported to contracts/openapi.json").
TypeScript API types are generated from this file via openapi-typescript.

Usage (from repo root):
    cd apps/api && uv run python ../../scripts/export-openapi.py
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "apps" / "api"
OUT_FILE = ROOT_DIR / "contracts" / "openapi.json"

# Make the FastAPI app importable (apps/api is not a package)
sys.path.insert(0, str(API_DIR))


def main() -> None:
    from main import app  # noqa: E402  (imports after sys.path setup)

    spec = app.openapi()
    spec["info"]["description"] = (
        "AI Marketing Intelligence OS — authoritative API contract. "
        "Frontend API types are generated from this document (openapi-typescript)."
    )
    OUT_FILE.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"[OK] Exported {len(spec.get('paths', {}))} paths -> {OUT_FILE.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()

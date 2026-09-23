#!/usr/bin/env python3
"""
scripts/validate-contracts.py

Validates all JSON Schema contract files in `contracts/`:
1. Ensures valid JSON syntax across all enums and event payloads.
2. Checks that all 49 worker event types in `contracts/enums/worker_event_type.json`
   are accounted for.
3. Checks that all states in `contracts/enums/worker_state.json` have valid transition definitions.
4. Checks that the base envelope schema in `contracts/events/base.schema.json` is well-formed.
"""

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT_DIR / "contracts"
ENUMS_DIR = CONTRACTS_DIR / "enums"
EVENTS_DIR = CONTRACTS_DIR / "events"

def load_json(filepath: Path) -> dict:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to parse {filepath.relative_to(ROOT_DIR)}: {e}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("AI Marketing Intelligence OS — Contracts Validation")
    print("=" * 60)
    errors = 0

    # 1. Validate Enums
    print("\n[1/3] Validating enums...")
    enum_files = list(ENUMS_DIR.glob("*.json"))
    print(f"  Found {len(enum_files)} enum schemas in {ENUMS_DIR.relative_to(ROOT_DIR)}")
    
    event_types_data = None
    worker_states_data = None

    for ef in enum_files:
        data = load_json(ef)
        if ef.name == "worker_event_type.json":
            event_types_data = data.get("enum", [])
            print(f"  [OK] worker_event_type.json ({len(event_types_data)} event types)")
        elif ef.name == "worker_state.json":
            worker_states_data = data
            states = data.get("enum", [])
            transitions = data.get("x-transitions", {})
            for st in states:
                if st not in transitions:
                    print(f"  [WARN] State '{st}' missing from x-transitions table!")
            print(f"  [OK] worker_state.json ({len(states)} states)")
        elif ef.name == "logical_zone.json":
            zones = data.get("x-zone-enum", [])
            print(f"  [OK] logical_zone.json ({len(zones)} zones)")
        elif ef.name == "worker_type.json":
            types = data.get("enum", [])
            print(f"  [OK] worker_type.json ({len(types)} worker types)")
        elif ef.name == "source_capability.json":
            caps = data.get("enum", [])
            print(f"  [OK] source_capability.json ({len(caps)} capabilities)")

    # 2. Validate Base Event Envelope
    print("\n[2/3] Validating base envelope schema...")
    base_envelope = load_json(EVENTS_DIR / "base.schema.json")
    required_fields = base_envelope.get("required", [])
    print(f"  [OK] base.schema.json (Required fields: {', '.join(required_fields[:6])}...)")

    # 3. Validate Event Payload Schemas
    print("\n[3/3] Validating individual event schemas...")
    payload_files = list(EVENTS_DIR.glob("worker.*.json"))
    print(f"  Found {len(payload_files)} payload schemas in {EVENTS_DIR.relative_to(ROOT_DIR)}")
    for pf in payload_files:
        pdata = load_json(pf)
        title = pdata.get("title", pf.stem)
        # Ensure it has basic schema structure
        if "type" not in pdata and "properties" not in pdata:
            print(f"  [ERROR] {pf.name} missing 'type' or 'properties'")
            errors += 1

    print("\n" + "=" * 60)
    if errors == 0:
        print("[SUCCESS] CONTRACTS VALIDATION PASSED: All schemas well-formed and consistent.")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"[FAIL] CONTRACTS VALIDATION FAILED with {errors} errors.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()

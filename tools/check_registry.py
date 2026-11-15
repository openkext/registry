#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check every file in the registry and write catalog.json.

    check_registry.py [OUT_JSON]     (default: build/catalog.json)
"""
import os
import sys

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, root)
from openkext_registry import catalog  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "build", "catalog.json")
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
errors = catalog.write(root, out)
for e in errors:
    print(f"error: {e}")
print(f"{'FAILED' if errors else 'OK'}: wrote {out}")
sys.exit(1 if errors else 0)

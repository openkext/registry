#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Write schema/kext.schema.json and schema/report.schema.json from openkext_registry/model.py.

    make_schemas.py          write the files
    make_schemas.py --check  exit 1 if the committed files are out of date (used by the tests)

The schemas describe the TOML files as JSON so that tools and LLM agents can validate
entries; model.py stays the authoritative check.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from openkext_registry import model as m  # noqa: E402

S = "https://json-schema.org/draft/2020-12/schema"
BASE = "https://openkext.org/schema/"


def s(pat=None, maxlen=None, **k):
    d = {"type": "string"}
    if pat is not None:
        d["pattern"] = pat if isinstance(pat, str) else pat.pattern
    if maxlen:
        d["maxLength"] = maxlen
    d.update(k)
    return d


def arr(item, **k):
    return {"type": "array", "items": item, "uniqueItems": True, **k}


DATE = {"type": "string", "format": "date", "description": "TOML date (YYYY-MM-DD); JSON copies use the ISO string"}


def kext_schema():
    return {
        "$schema": S, "$id": BASE + "kext.schema.json",
        "title": "OpenKext project entry (kexts/<id>/kext.toml)",
        "description": "Schema of a registry entry, expressed as JSON. The files are TOML; "
                       "openkext_registry/model.py is the authoritative check.",
        "type": "object", "additionalProperties": False,
        "required": ["id", "name", "summary", "kind", "categories", "source", "license", "maintainers",
                     "ai_disclosure", "macos", "releases"],
        "properties": {
            "id": s(m.ID_RE, 50, description="Lowercase id; equals the directory name"),
            "name": s(maxlen=80),
            "summary": s(maxlen=280),
            "kind": {"enum": sorted(m.KINDS)},
            "categories": arr({"enum": sorted(m.CATEGORIES)}, minItems=1, maxItems=5),
            "source": s(m.GITHUB_REPO_RE, 150, description="Public GitHub repository URL"),
            "license": {"enum": sorted(m.LICENSES),
                        "description": "SPDX id. Other open-source licenses are possible but go to manual review."},
            "license_file": s(maxlen=200, description="Path of the license text in the repository"),
            "maintainers": arr(s(m.LOGIN_RE), minItems=1, maxItems=10),
            "ai_disclosure": s(maxlen=280, description="AI tools and models used, or 'none'"),
            "homepage": s("^https://", 200),
            "based_on": arr(s("^https://"), maxItems=20),
            "hardware": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["vendor", "description"],
                "properties": {"vendor": s(maxlen=40), "description": s(maxlen=120),
                               "pci_ids": arr(s(m.HW_ID_RE), maxItems=64),
                               "usb_ids": arr(s(m.HW_ID_RE), maxItems=64)}}},
            "macos": {"type": "object", "additionalProperties": False, "required": ["min", "max"],
                      "properties": {"min": s(m.MACOS_RE), "max": s(m.MACOS_RE)}},
            "releases": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["version", "tag", "date", "assets"],
                "properties": {
                    "version": s(m.VERSION_RE, 41), "tag": s(maxlen=100), "date": DATE, "notes": s(maxlen=500),
                    "assets": {"type": "array", "minItems": 1, "items": {
                        "type": "object", "additionalProperties": False, "required": ["name", "sha256"],
                        "properties": {"name": s(maxlen=200), "sha256": s(m.SHA256_RE),
                                       "macos": s(maxlen=20)}}}}}},
        },
    }


def report_schema():
    return {
        "$schema": S, "$id": BASE + "report.schema.json",
        "title": "OpenKext test report (kexts/<id>/reports/<login>/<name>.toml)",
        "description": "Schema of a test report, expressed as JSON. The files are TOML; "
                       "openkext_registry/model.py is the authoritative check.",
        "type": "object", "additionalProperties": False,
        "required": ["kext", "version", "result", "date", "macos", "hardware"],
        "properties": {
            "kext": s(m.ID_RE),
            "version": s(maxlen=41, description="A release version listed in the kext's entry"),
            "asset": s(maxlen=200),
            "result": {"enum": sorted(m.RESULTS)},
            "date": DATE,
            "notes": s(maxlen=2000),
            "macos": {"type": "object", "additionalProperties": False, "required": ["version", "build"],
                      "properties": {"version": s(m.MACOS_RE), "build": s(m.BUILD_RE)}},
            "hardware": {"type": "object", "additionalProperties": False, "required": ["cpu", "smbios"],
                         "properties": {"cpu": s(maxlen=80), "smbios": s(maxlen=40), "bootloader": s(maxlen=60),
                                        "board": s(maxlen=80), "device_ids": arr(s(m.HW_ID_RE), maxItems=16)}},
            "features": {"type": "object", "maxProperties": 30,
                         "propertyNames": {"pattern": "^[a-z0-9][a-z0-9-]{0,30}$"},
                         "additionalProperties": {"enum": sorted(m.FEATURE_STATES)}},
        },
    }


def render():
    return {name: json.dumps(fn(), indent=2) + "\n"
            for name, fn in (("kext", kext_schema), ("report", report_schema))}


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for name, text in render().items():
        path = os.path.join(ROOT, "schema", f"{name}.schema.json")
        if check:
            try:
                with open(path) as f:
                    if f.read() != text:
                        stale.append(path)
            except FileNotFoundError:
                stale.append(path)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
    if stale:
        print("out of date (run tools/make_schemas.py):", *stale)
        sys.exit(1)


if __name__ == "__main__":
    main()

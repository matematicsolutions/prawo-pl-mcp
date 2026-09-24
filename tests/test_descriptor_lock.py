"""Descriptor lock - the tool surface a client sees must not change silently.

Clients that pin tool descriptors (PATRON's MCP gateway treats a changed
description or schema as drift and holds the connector for review) break when
a release changes a descriptor nobody meant to change: a reworded docstring, a
new optional field, a different schema from a fastmcp upgrade. This test makes
every such change visible in the diff of `tests/tools.lock.json` before it
reaches PyPI.

Descriptors are read through the public in-memory client, i.e. exactly what a
client receives over `tools/list`, then normalised (keys sorted, tools sorted
by name). The digest is computed from that JSON, never from file bytes, so
line endings cannot change it.

Intentional change: regenerate and commit the lock together with a version bump.

    python tests/test_descriptor_lock.py --update
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tomllib
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).parent.parent
LOCK = Path(__file__).parent / "tools.lock.json"


async def _descriptors() -> dict[str, dict]:
    from prawo_pl_mcp.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
    return {
        t.name: t.model_dump(mode="json", exclude_none=True)
        for t in sorted(tools, key=lambda t: t.name)
    }


def _digest(obj: object) -> str:
    canon = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _build_lock(descriptors: dict[str, dict]) -> dict:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    return {
        "package_version": version,
        "toolset_sha256": _digest(descriptors),
        "tools": {name: {"sha256": _digest(d), "descriptor": d} for name, d in descriptors.items()},
    }


def test_descriptors_match_lock():
    assert LOCK.exists(), (
        "tests/tools.lock.json is missing - an empty baseline would pass every change. "
        "Generate it: python tests/test_descriptor_lock.py --update"
    )
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assert lock.get("tools"), "tools.lock.json lists no tools - refusing an empty baseline."

    current = asyncio.run(_descriptors())
    locked = {name: entry["descriptor"] for name, entry in lock["tools"].items()}

    added = sorted(set(current) - set(locked))
    removed = sorted(set(locked) - set(current))
    changed = sorted(
        n for n in set(current) & set(locked) if _digest(current[n]) != _digest(locked[n])
    )
    assert not (added or removed or changed), (
        f"Tool descriptors drifted from tests/tools.lock.json: added={added} "
        f"removed={removed} changed={changed}. If intended, bump the version and run "
        "python tests/test_descriptor_lock.py --update"
    )
    assert lock["toolset_sha256"] == _digest(current)


if __name__ == "__main__":
    if "--update" not in sys.argv:
        sys.exit("usage: python tests/test_descriptor_lock.py --update")
    lock = _build_lock(asyncio.run(_descriptors()))
    LOCK.write_text(
        json.dumps(lock, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {LOCK} ({len(lock['tools'])} tools, version {lock['package_version']})")

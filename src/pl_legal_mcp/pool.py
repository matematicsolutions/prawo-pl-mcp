"""Lazy pula klientow MCP do konektorow floty (podprocesy stdio).

Drabinka provisioning (regula floty - lazy-provisioning obowiazkowy,
zaden tool nie bleduje "konektor niezainstalowany"):
1. env override `PL_LEGAL_MCP_CMD_<ID>` (np. lokalny checkout: `python -m sejm_eli_mcp`)
2. zywa sesja w puli (keep-alive po pierwszym uzyciu)
3. spawn `uvx <pkg>` / `npx -y <pkg>` - manager pakietow sam pobiera przy 1. uzyciu
4. czytelny blad `source_unavailable` (brak Node/uv, pakiet nieosiagalny)
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from .registry import Source

# Pierwsze wywolanie zrodla moze pobierac pakiet z npm/PyPI - dajemy zapas.
INIT_TIMEOUT_S = float(os.environ.get("PL_LEGAL_MCP_INIT_TIMEOUT", "180"))
CALL_TIMEOUT_S = float(os.environ.get("PL_LEGAL_MCP_TIMEOUT", "90"))


class SourceUnavailable(Exception):
    """Zrodlo nieosiagalne po przejsciu calej drabinki provisioning."""


def _spawn_spec(source: Source) -> tuple[str, list[str]]:
    """Komenda spawnu wg drabinki: env override -> runtime z registry."""
    override = os.environ.get(f"PL_LEGAL_MCP_CMD_{source.id.upper().replace('-', '_')}")
    if override:
        parts = shlex.split(override, posix=False)
        return parts[0], parts[1:]
    if source.runtime == "npx":
        return "npx", ["-y", source.package]
    if source.runtime == "uvx":
        return "uvx", [source.package]
    raise SourceUnavailable(f"Unknown runtime '{source.runtime}' for source '{source.id}'")


def _runtime_present(command: str) -> bool:
    return shutil.which(command) is not None


class SourcePool:
    """Trzyma po jednej zywej sesji MCP na zrodlo. Spawn lazy, na 1. wywolanie."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _lock_for(self, source_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if source_id not in self._locks:
                self._locks[source_id] = asyncio.Lock()
            return self._locks[source_id]

    async def get_client(self, source: Source) -> Client:
        lock = await self._lock_for(source.id)
        async with lock:
            client = self._clients.get(source.id)
            if client is not None and client.is_connected():
                return client

            command, args = _spawn_spec(source)
            if not _runtime_present(command):
                hint = {
                    "npx": "Node.js >= 18 (npx) not found on PATH",
                    "uvx": "uv (uvx) not found on PATH",
                }.get(source.runtime, f"'{command}' not found on PATH")
                raise SourceUnavailable(
                    f"Source '{source.id}' needs {hint}. Install the runtime or set "
                    f"PL_LEGAL_MCP_CMD_{source.id.upper().replace('-', '_')} to a local command."
                )

            transport = StdioTransport(command=command, args=args, keep_alive=True)
            client = Client(transport, timeout=CALL_TIMEOUT_S)
            try:
                await asyncio.wait_for(client.__aenter__(), timeout=INIT_TIMEOUT_S)
            except Exception as exc:  # spawn/handshake failed - czytelny blad, nie traceback
                raise SourceUnavailable(
                    f"Source '{source.id}' failed to start ({command} {' '.join(args)}): {exc}"
                ) from exc
            self._clients[source.id] = client
            return client

    async def call(self, source: Source, tool: str, arguments: dict) -> str:
        """Wywolaj natywny tool konektora, zwroc tekst.

        Konektory zwracaja rozne ksztalty: text content blocks (TS-owe),
        structured content (FastMCP przy dict/list returns) - bierzemy tekst,
        a gdy pusty, serializujemy structured content do JSON.
        """
        client = await self.get_client(source)
        result = await client.call_tool(tool, arguments)
        parts: list[str] = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
        structured = getattr(result, "structured_content", None)
        if structured is not None:
            # FastMCP owija nie-dict wyniki w {"result": ...}
            if isinstance(structured, dict) and set(structured) == {"result"}:
                structured = structured["result"]
            return json.dumps(structured, ensure_ascii=False, default=str)
        data = getattr(result, "data", None)
        if data is not None:
            return json.dumps(data, ensure_ascii=False, default=str)
        return ""

    async def list_tools(self, source: Source) -> list[dict]:
        """Zywy tools/list konektora (lazy spawn) - schematy do wgladu dla LLM."""
        client = await self.get_client(source)
        tools = await client.list_tools()
        return [
            {
                "name": t.name,
                "description": (t.description or "").strip(),
                "input_schema": t.inputSchema,
            }
            for t in tools
        ]

    async def close_all(self) -> None:
        for source_id, client in list(self._clients.items()):
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass
            self._clients.pop(source_id, None)


POOL = SourcePool()

"""ASGI app - remote Streamable HTTP (parytet yargi-mcp: remote bez auth mozliwy).

Uruchamianie:
    uvicorn pl_legal_mcp.asgi:app --host 0.0.0.0 --port 8000

Auth opcjonalny, dwukanalowy (kanon floty): jesli env PL_LEGAL_MCP_API_KEY jest
ustawiony, kazdy request musi niesc `X-API-Key: <key>` LUB
`Authorization: Bearer <key>` (niektorzy klienci wysylaja tylko jeden z nich).
Bez env - serwer otwarty (dane publiczne, read-only).
"""

from __future__ import annotations

import hmac
import os

from .server import mcp

_inner = mcp.http_app()


async def app(scope, receive, send):
    if scope["type"] != "http":
        await _inner(scope, receive, send)
        return

    expected = os.environ.get("PL_LEGAL_MCP_API_KEY")
    if expected:
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        supplied = headers.get("x-api-key")
        if not supplied:
            auth = headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                supplied = auth.split(" ", 1)[1].strip()
        if not supplied or not hmac.compare_digest(supplied, expected):
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            })
            await send({
                "type": "http.response.body",
                "body": b"Missing or invalid API key - send X-API-Key or Authorization: Bearer <key>",
            })
            return

    await _inner(scope, receive, send)

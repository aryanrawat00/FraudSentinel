"""Bound input buffering and prevent caching of investigation responses."""

from starlette.responses import JSONResponse


class InvestigationRequestLimits:
    def __init__(self, app, max_bytes=1_048_576):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/intelligence"):
            return await self.app(scope, receive, send)

        async def protected_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *[
                        (key, value)
                        for key, value in message.get("headers", [])
                        if key.lower() not in {b"cache-control", b"x-content-type-options"}
                    ],
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        buffered = []
        if scope["method"] in {"POST", "PATCH", "PUT"}:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > self.max_bytes:
                    response = JSONResponse({"detail": "Request body exceeds sandbox limit"}, 413)
                    return await response(scope, receive, protected_send)
                buffered.append(message)
                if not message.get("more_body", False):
                    break

        async def bounded_receive():
            return buffered.pop(0) if buffered else await receive()

        await self.app(scope, bounded_receive, protected_send)

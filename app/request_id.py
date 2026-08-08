# app/request_id.py
import uuid
from loguru import logger


class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # not an HTTP request (e.g. websocket, lifespan) — pass through untouched
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        incoming_id = headers.get(b"x-request-id")
        request_id = incoming_id.decode() if incoming_id else str(uuid.uuid4())

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        with logger.contextualize(request_id=request_id):
            await self.app(scope, receive, send_wrapper)
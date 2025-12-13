import logging
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from utils.request_context import get_request_id, reset_request_id, set_request_id


_request_logger = logging.getLogger("vector-stores.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid4())

        token = set_request_id(request_id)
        try:
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            _request_logger.info(
                "%s %s -> %s",
                request.method,
                request.url.path,
                getattr(response, "status_code", "unknown"),
            )
            return response
        finally:
            reset_request_id(token)


class AllowHostsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allow_hosts: list[str] | None = None):
        super().__init__(app)
        self._allow_hosts = [h.strip() for h in (allow_hosts or []) if h.strip()]

    def _get_client_ip(self, request: Request) -> str | None:
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            first = x_forwarded_for.split(",", 1)[0].strip()
            if first:
                return first

        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            x_real_ip = x_real_ip.strip()
            if x_real_ip:
                return x_real_ip

        return request.client.host if request.client else None

    async def dispatch(self, request: Request, call_next):
        if not self._allow_hosts:
            return await call_next(request)

        client_host = self._get_client_ip(request)

        header_host = request.headers.get("host")
        if header_host and ":" in header_host:
            header_host = header_host.split(":", 1)[0]

        if client_host not in self._allow_hosts and header_host not in self._allow_hosts:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Host not allowed",
                    "request_id": get_request_id(),
                },
            )

        return await call_next(request)

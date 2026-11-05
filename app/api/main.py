from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import admin, approvals, diagnose, incidents
from app.config import Settings, get_settings
from app.container import Container
from app.observability import telemetry
from app.security.errors import AccessDenied, AuthError, Conflict, NotFound
from app.services.diagnosis import ServiceUnavailable


def create_app(container: Container | None = None) -> FastAPI:
    settings: Settings = container.settings if container else get_settings()
    telemetry.configure_logging(settings.log_level)
    app = FastAPI(title="Industrial Maintenance AI", version="0.1.0")
    if container:
        app.state.container = container

    @app.middleware("http")
    async def trace_and_log(request: Request, call_next):
        trace_id = telemetry.new_id("TRC")
        telemetry.bind(trace_id=trace_id, path=request.url.path, method=request.method)
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        telemetry.log("http", "request", status=response.status_code, latency_ms=round((time.perf_counter() - t0) * 1000, 2))
        return response

    def _err(status: int, code: str, msg: str) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": code, "detail": msg, "trace_id": telemetry.current().get("trace_id")})

    def _audit_denial(request: Request, event: str, reason: str, incident_id: str | None = None) -> None:
        c = getattr(request.app.state, "container", None)
        if c is None:
            return
        try:
            c.audit.record(event, actor=getattr(request.state, "principal_id", "anonymous"), decision="denied",
                           incident_id=incident_id or request.path_params.get("incident_id"), details={"path": request.url.path, "method": request.method, "reason": reason})
        except Exception:  # noqa: BLE001  auditing must never turn a 403 into a 500
            telemetry.log("audit", "failed to record denial")

    @app.exception_handler(AuthError)
    async def _auth(request: Request, e: AuthError):
        _audit_denial(request, "authentication_failed", str(e))
        r = _err(401, "unauthorized", str(e))
        r.headers["WWW-Authenticate"] = "Bearer"
        return r

    @app.exception_handler(AccessDenied)
    async def _denied(request: Request, e: AccessDenied):
        _audit_denial(request, "authorization_denied", str(e), e.incident_id)
        return _err(403, "forbidden", str(e))

    @app.exception_handler(NotFound)
    async def _nf(_: Request, e: NotFound):
        return _err(404, "not_found", str(e))

    @app.exception_handler(Conflict)
    async def _conflict(_: Request, e: Conflict):
        return _err(409, "conflict", str(e))

    @app.exception_handler(ServiceUnavailable)
    async def _unavail(_: Request, e: ServiceUnavailable):
        return _err(503, "upstream_unavailable", str(e))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env, "llm": settings.llm_mode, "store": settings.store_mode}

    for r in (diagnose.router, incidents.router, approvals.router, admin.router):
        app.include_router(r)
    return app


app = create_app()

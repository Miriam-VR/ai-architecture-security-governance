from __future__ import annotations

from fastapi import Depends, Header, Request

from app.config import get_settings
from app.container import Container, build_container
from app.models import Principal
from app.security.authentication import verify_token
from app.security.errors import AuthError


def get_container(request: Request) -> Container:
    c = getattr(request.app.state, "container", None)
    if c is None:  # lazy: built on first request (Lambda cold start) so import never touches the network
        c = request.app.state.container = build_container(get_settings())
    return c


def get_principal(request: Request, authorization: str | None = Header(default=None), c: Container = Depends(get_container)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    p = verify_token(authorization.split(" ", 1)[1].strip(), c.settings)
    request.state.principal_id = p.user_id
    return p

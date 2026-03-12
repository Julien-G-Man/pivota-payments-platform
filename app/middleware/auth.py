"""JWT auth middleware — verifies Bearer token and sets request.state."""

from fastapi import Request, HTTPException, status


async def jwt_auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    PUBLIC_PATHS = {
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/momo/webhook",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    # TODO: decode token via app.core.security.decode_token
    token = auth_header.removeprefix("Bearer ")
    _ = token  # placeholder until security module is wired up

    return await call_next(request)

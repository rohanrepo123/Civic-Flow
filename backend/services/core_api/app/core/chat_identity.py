"""Authenticated user identity, or a signed browser identity in local demo mode."""

from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.core.dependencies import bearer, current_claims
from app.core.config import settings
from app.core.security import create_access_token, decode_token


async def chat_identity(request: Request, response: Response,
                        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UUID:
    if credentials is not None or settings.ENFORCE_AUTH:
        claims = await current_claims(credentials)
        return uuid5(NAMESPACE_URL, "civicflow-user:" + str(claims["sub"]))
    token = request.cookies.get("civicflow_chat_identity", "")
    try:
        claims = decode_token(token)
        if claims.get("scope") != "local-chat":
            raise ValueError("Wrong identity scope")
        return UUID(claims["sub"])
    except Exception:
        identity = uuid4()
        token = create_access_token({"sub": str(identity), "scope": "local-chat"}, timedelta(days=30))
        response.set_cookie("civicflow_chat_identity", token, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https", max_age=30 * 86400)
        return identity

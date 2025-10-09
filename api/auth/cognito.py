import time, json, base64, requests, hashlib
from functools import lru_cache
from typing import Any, Dict
from fastapi import HTTPException, status
from jose import jwk
from jose.utils import base64url_decode
import os

POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
REGION = os.getenv("COGNITO_REGION", "")
AUDIENCE = os.getenv("COGNITO_AUDIENCE")  # optional
JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}/.well-known/jwks.json"

@lru_cache(maxsize=1)
def _fetch_jwks():
    resp = requests.get(JWKS_URL, timeout=5)
    resp.raise_for_status()
    return resp.json()["keys"]

def verify_id_token(id_token: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = id_token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed token")

    header = json.loads(base64.urlsafe_b64decode(header_b64 + "=="))
    kid = header.get("kid")
    keys = _fetch_jwks()
    key = next((k for k in keys if k["kid"] == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Unknown key")

    message = f"{header_b64}.{payload_b64}".encode()
    signature = base64url_decode(sig_b64.encode())
    public_key = jwk.construct(key)
    if not public_key.verify(message, signature):
        raise HTTPException(status_code=401, detail="Bad signature")

    payload_raw = base64.urlsafe_b64decode(payload_b64 + "==")
    claims = json.loads(payload_raw)

    now = int(time.time())
    if now > claims.get("exp", 0):
        raise HTTPException(status_code=401, detail="Token expired")
    if claims.get("iss") != f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}":
        raise HTTPException(status_code=401, detail="Bad issuer")
    if AUDIENCE and claims.get("aud") != AUDIENCE:
        raise HTTPException(status_code=401, detail="Bad audience")

    return claims
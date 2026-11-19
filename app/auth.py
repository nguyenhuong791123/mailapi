"""Bearer access tokens issued by the token server (wso2), verified like the API server does."""
import logging

import jwt
from flask import Flask, g, request

from .config import AuthConfig
from .errors import ApiError

log = logging.getLogger(__name__)

PUBLIC_PATHS = ('/', '/health')


class TokenVerifier:
    def __init__(self, cfg: AuthConfig):
        self.cfg = cfg
        # Keys are cached by the client and refetched for an unknown `kid` (key rotation).
        self.jwks = jwt.PyJWKClient(cfg.jwks_uri, cache_keys=True, lifespan=600) if cfg.jwks_uri else None

    def _key(self, token: str):
        if self.jwks:
            return self.jwks.get_signing_key_from_jwt(token).key
        if self.cfg.public_key:
            return self.cfg.public_key
        if self.cfg.secret:
            return self.cfg.secret
        raise ApiError('Token verification is not configured', 500)

    def verify(self, token: str) -> dict:
        claims = jwt.decode(
            token,
            self._key(token),
            algorithms=self.cfg.algorithms,
            issuer=self.cfg.issuer or None,
            audience=self.cfg.audience or None,
            options={'require': ['exp'], 'verify_aud': bool(self.cfg.audience)},
        )
        if claims.get('uid') is None or claims.get('cid') is None:
            raise jwt.InvalidTokenError('Missing claims')
        return claims


def bearer_token() -> str:
    header = request.headers.get('Authorization', '')
    scheme, _, token = header.partition(' ')
    return token.strip() if scheme.lower() == 'bearer' else ''


def init_auth(app: Flask, cfg: AuthConfig) -> None:
    """Every request except the status pages needs a valid access token."""
    if not cfg.required:
        log.warning('AUTH_REQUIRED=false: requests are not authenticated (local use only)')
    verifier = TokenVerifier(cfg)

    @app.before_request
    def _authenticate():
        g.user = None
        if request.method == 'OPTIONS' or request.path in PUBLIC_PATHS or not cfg.required:
            return None
        token = bearer_token()
        if not token:
            raise ApiError('Access token is missing', 401)
        try:
            claims = verifier.verify(token)
        except ApiError:
            raise
        except Exception as err:  # invalid signature, expired, unreachable JWKS, ...
            log.warning('Token rejected: %s', err)
            raise ApiError('Access token is missing or invalid', 401) from None
        g.user = {'uid': claims.get('uid'), 'cid': claims.get('cid'), 'tenant': claims.get('client_id')}
        return None

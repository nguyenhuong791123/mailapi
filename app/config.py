"""Settings, read from environment variables only (no credentials in code or JSON files)."""
import os
from dataclasses import dataclass, field


def env_str(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    value = env_str(name)
    try:
        return int(value) if value else default
    except ValueError as err:
        raise ValueError(f'{name} must be an integer: {value!r}') from err


def env_bool(name: str, default: bool) -> bool:
    value = env_str(name).lower()
    if not value:
        return default
    return value in ('1', 'true', 'yes', 'on')


def env_list(name: str) -> list:
    return [v.strip() for v in env_str(name).split(',') if v.strip()]


SECURITY_MODES = ('ssl', 'starttls', 'none')


@dataclass(frozen=True)
class Server:
    """One mail server (SMTP / IMAP / POP3)."""
    host: str
    port: int
    security: str
    username: str
    password: str

    @property
    def configured(self) -> bool:
        return bool(self.host)


def _server(prefix: str, port: int, security: str, fallback: 'Server | None' = None) -> Server:
    sec = env_str(f'{prefix}_SECURITY', security).lower()
    if sec not in SECURITY_MODES:
        raise ValueError(f'{prefix}_SECURITY must be one of {SECURITY_MODES}: {sec!r}')
    # IMAP / POP3 usually use the same account as SMTP.
    user = env_str(f'{prefix}_USER', fallback.username if fallback else '')
    password = env_str(f'{prefix}_PASSWORD', fallback.password if fallback else '')
    return Server(env_str(f'{prefix}_HOST'), env_int(f'{prefix}_PORT', port), sec, user, password)


@dataclass(frozen=True)
class AuthConfig:
    """Access tokens of the token server (same settings as the API server `be`)."""
    required: bool
    jwks_uri: str
    public_key: str
    secret: str
    algorithms: list
    issuer: str
    audience: str


@dataclass(frozen=True)
class Config:
    smtp: Server
    imap: Server
    pop3: Server
    imap_mailbox: str
    timeout: int
    max_mails: int
    max_recipients: int
    max_fetch: int
    max_content_length: int
    cors_origins: list
    auth: AuthConfig = field(repr=False)
    # Mail accounts per tenant from the API server (be /internal/mail-servers/<tenant>); empty: the
    # MAIL_* accounts above are used for every tenant.
    settings_uri: str = ''
    internal_secret: str = field(default='', repr=False)
    settings_ttl: int = 60

    @classmethod
    def from_env(cls) -> 'Config':
        smtp = _server('MAIL_SMTP', 587, 'starttls')
        jwks = env_str('JWT_JWKS_URI')
        public_key = env_str('JWT_PUBLIC_KEY').replace('\\n', '\n')
        secret = env_str('JWT_SECRET')
        default_alg = 'HS256' if secret and not (jwks or public_key) else 'RS256'
        return cls(
            smtp=smtp,
            imap=_server('MAIL_IMAP', 993, 'ssl', smtp),
            pop3=_server('MAIL_POP3', 995, 'ssl', smtp),
            imap_mailbox=env_str('MAIL_IMAP_MAILBOX', 'INBOX'),
            timeout=env_int('MAIL_TIMEOUT', 15),
            max_mails=env_int('MAIL_MAX_MAILS', 20),
            max_recipients=env_int('MAIL_MAX_RECIPIENTS', 50),
            max_fetch=env_int('MAIL_MAX_FETCH', 100),
            max_content_length=env_int('MAX_CONTENT_MB', 25) * 1024 * 1024,
            cors_origins=env_list('CORS_ORIGINS'),
            auth=AuthConfig(
                required=env_bool('AUTH_REQUIRED', True),
                jwks_uri=jwks,
                public_key=public_key,
                secret=secret,
                algorithms=env_list('JWT_ALGORITHMS') or [default_alg],
                issuer=env_str('JWT_ISSUER'),
                audience=env_str('JWT_AUDIENCE'),
            ),
            settings_uri=env_str('SERVER_SETTINGS_URI').rstrip('/'),
            internal_secret=env_str('INTERNAL_API_SECRET'),
            settings_ttl=env_int('SERVER_SETTINGS_TTL', 60),
        )

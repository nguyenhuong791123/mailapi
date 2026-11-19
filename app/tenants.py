"""Mail accounts of each tenant, from the API server (サーバー情報 of the tenant DB).

be `GET /internal/mail-servers/<tenant>` (header X-Internal-Secret) returns the tenant's E-mail
servers: `{"smtp": {host, port, username, password, security}, "pop3": {...}}` (null when not set).
They are cached for `SERVER_SETTINGS_TTL` seconds. Without `SERVER_SETTINGS_URI` the accounts of the
environment (MAIL_*) are used for every tenant.
"""
import dataclasses
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request

from .config import SECURITY_MODES, Config, Server
from .errors import ApiError

log = logging.getLogger(__name__)
TENANT = re.compile(r'^[a-z0-9-]{1,30}$', re.I)
NOT_SET = Server('', 0, 'none', '', '')


def _server(d) -> Server:
    if not isinstance(d, dict) or not d.get('host'):
        return NOT_SET
    security = str(d.get('security') or 'starttls').lower()
    if security not in SECURITY_MODES:
        security = 'starttls'
    return Server(str(d['host']), int(d.get('port') or 0), security, str(d.get('username') or ''), str(d.get('password') or ''))


class TenantServers:
    def __init__(self, cfg: Config, fetch=None):
        self.cfg = cfg
        self._fetch = fetch or self._http
        self._cache = {}
        self._lock = threading.Lock()

    def _http(self, tenant: str) -> dict:
        req = urllib.request.Request(f'{self.cfg.settings_uri}/{tenant}',
                                     headers={'X-Internal-Secret': self.cfg.internal_secret})
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return json.loads(res.read().decode('utf-8'))
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return {}
            log.warning('Mail servers of %s: HTTP %s', tenant, err.code)
            raise ApiError('Mail server settings are not available', 503) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            log.warning('Mail servers of %s: %s', tenant, err)
            raise ApiError('Mail server settings are not available', 503) from None

    def config_for(self, tenant) -> Config:
        """The configuration with the tenant's SMTP / POP3 accounts (IMAP is not set per tenant)."""
        if not self.cfg.settings_uri:
            return self.cfg
        if not tenant or not TENANT.match(str(tenant)):
            raise ApiError('The tenant of the access token is unknown', 401)
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(tenant)
            if hit and hit[0] > now:
                return hit[1]
        data = self._fetch(str(tenant)) or {}
        cfg = dataclasses.replace(self.cfg, smtp=_server(data.get('smtp')), pop3=_server(data.get('pop3')), imap=NOT_SET)
        with self._lock:
            self._cache[tenant] = (now + max(0, self.cfg.settings_ttl), cfg)
        return cfg

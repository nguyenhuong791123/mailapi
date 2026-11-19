import datetime as dt
import sys
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.config import AuthConfig, Config, Server  # noqa: E402

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_PEM = KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def make_token(**claims):
    now = dt.datetime.now(dt.timezone.utc)
    payload = {'uid': 1, 'cid': 3, 'client_id': 'edu', 'exp': now + dt.timedelta(minutes=5), **claims}
    return jwt.encode(payload, KEY, algorithm='RS256')


def make_config(**overrides) -> Config:
    base = dict(
        smtp=Server('smtp.test', 587, 'starttls', 'user', 'secret'),
        imap=Server('', 993, 'ssl', '', ''),
        pop3=Server('', 995, 'ssl', '', ''),
        imap_mailbox='INBOX', timeout=5, max_mails=5, max_recipients=3, max_fetch=50,
        max_content_length=5 * 1024 * 1024, cors_origins=[],
        auth=AuthConfig(True, '', PUBLIC_PEM, '', ['RS256'], '', ''),
    )
    base.update(overrides)
    return Config(**base)


class FakeSMTP:
    """Stands in for smtplib.SMTP; records what would be sent.

    `extensions`: what the server offers before TLS (after STARTTLS it also offers AUTH, like Gmail).
    """
    sent = []
    logins = []
    events = []
    extensions = {'starttls', 'auth'}
    wrong_password = False

    def __init__(self, host, port, timeout=None, **_):
        self.host, self.port = host, port
        self.tls = False
        FakeSMTP.events.append(('connect', type(self).__name__, port))

    def ehlo(self, name=''):
        pass

    def has_extn(self, name):
        offered = set(FakeSMTP.extensions) | ({'auth'} if self.tls and 'starttls' in FakeSMTP.extensions else set())
        return name.lower() in offered

    def starttls(self, context=None):
        self.tls = True
        FakeSMTP.events.append(('starttls',))

    def close(self):
        pass

    def login(self, user, password):
        import smtplib
        if FakeSMTP.wrong_password:
            raise smtplib.SMTPAuthenticationError(535, b'5.7.8 Username and Password not accepted')
        FakeSMTP.logins.append(user)

    def send_message(self, msg, from_addr=None, to_addrs=None):
        FakeSMTP.sent.append((msg, from_addr, to_addrs))

    def quit(self):
        pass


class FakeSMTPSSL(FakeSMTP):
    def __init__(self, host, port, timeout=None, context=None, **_):
        super().__init__(host, port, timeout)
        self.tls = True


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.logins, FakeSMTP.events = [], [], []
    FakeSMTP.extensions, FakeSMTP.wrong_password = {'starttls', 'auth'}, False
    monkeypatch.setattr('smtplib.SMTP', FakeSMTP)
    monkeypatch.setattr('smtplib.SMTP_SSL', FakeSMTPSSL)
    return FakeSMTP


@pytest.fixture
def client():
    return create_app(make_config()).test_client()


@pytest.fixture
def auth():
    return {'Authorization': f'Bearer {make_token()}'}

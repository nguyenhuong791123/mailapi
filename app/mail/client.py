"""SMTP sending and IMAP / POP3 receiving. Server accounts come from the configuration only."""
import imaplib
import logging
import poplib
import smtplib
import ssl
from contextlib import contextmanager
from email import message_from_bytes, policy

from ..config import Config, Server
from ..errors import ApiError
from .message import build_message, summarize

log = logging.getLogger(__name__)


def _require(server: Server, name: str) -> None:
    if not server.configured:
        raise ApiError(f'{name} server is not configured', 503)


# Ports that use TLS from the first byte (SMTPS / POP3S), whatever the encryption setting says.
SMTP_SSL_PORTS = (465,)
POP3_SSL_PORTS = (995,)

# Error codes (labels of the front-end: apiErrors)
SMTP_CONNECT_FAILED = 'MAIL_SMTP_CONNECT_FAILED'   # host / port unreachable, timeout
SMTP_TLS_FAILED = 'MAIL_SMTP_TLS_FAILED'           # TLS negotiation / certificate
SMTP_NO_TLS = 'MAIL_SMTP_NO_TLS'                   # encryption tls set, the server offers no STARTTLS
SMTP_NO_AUTH = 'MAIL_SMTP_NO_AUTH'                 # the server accepts no login on this connection
SMTP_AUTH_FAILED = 'MAIL_SMTP_AUTH_FAILED'         # wrong user / password (Gmail: app password needed)
POP3_CONNECT_FAILED = 'MAIL_POP3_CONNECT_FAILED'
POP3_AUTH_FAILED = 'MAIL_POP3_AUTH_FAILED'


def _smtp_open(server: Server, timeout: int, implicit_tls: bool):
    ctx = ssl.create_default_context()
    if implicit_tls:
        client = smtplib.SMTP_SSL(server.host, server.port, timeout=timeout, context=ctx)
        client.ehlo()
        return client
    client = smtplib.SMTP(server.host, server.port, timeout=timeout)
    client.ehlo()
    if client.has_extn('starttls'):
        # Also with encryption "none": most servers (Gmail, Outlook, ...) offer login only over TLS.
        client.starttls(context=ctx)
        client.ehlo()
    elif server.security == 'starttls':
        client.close()
        raise ApiError(SMTP_NO_TLS, 502)
    return client


@contextmanager
def _smtp(server: Server, timeout: int):
    """A logged-in SMTP connection to any server: SSL (port 465 or "ssl"), else STARTTLS when offered."""
    implicit_tls = server.security == 'ssl' or server.port in SMTP_SSL_PORTS
    try:
        try:
            client = _smtp_open(server, timeout, implicit_tls)
        except ssl.SSLError:
            if not implicit_tls or server.port in SMTP_SSL_PORTS:
                raise
            # "ssl" set for a STARTTLS port (587 / 25): retry as STARTTLS
            client = _smtp_open(server, timeout, False)
    except ApiError:
        raise
    except (ssl.SSLError, ssl.CertificateError) as err:
        log.error('SMTP TLS failed (%s:%s): %s', server.host, server.port, err)
        raise ApiError(SMTP_TLS_FAILED, 502) from None
    except (OSError, smtplib.SMTPException) as err:
        log.error('SMTP connection failed (%s:%s): %s', server.host, server.port, err)
        raise ApiError(SMTP_CONNECT_FAILED, 502) from None
    try:
        if server.username:
            if not client.has_extn('auth'):
                log.error('SMTP server %s:%s offers no login (AUTH)', server.host, server.port)
                raise ApiError(SMTP_NO_AUTH, 502)
            try:
                client.login(server.username, server.password)
            except smtplib.SMTPAuthenticationError as err:
                log.error('SMTP login failed for %s@%s: %s', server.username, server.host, err)
                raise ApiError(SMTP_AUTH_FAILED, 502) from None
        yield client
    finally:
        try:
            client.quit()
        except (OSError, smtplib.SMTPException):
            pass


def send_mails(cfg: Config, mails) -> list:
    """Sends each mail over one connection; one `{flag, msg}` per mail (invalid mails are not sent)."""
    _require(cfg.smtp, 'SMTP')
    if not isinstance(mails, list) or not mails:
        raise ApiError('mails is required')
    if len(mails) > cfg.max_mails:
        raise ApiError(f'Too many mails (max {cfg.max_mails})')

    built = []
    for mail in mails:
        try:
            built.append(build_message(mail, cfg.max_recipients))
        except ApiError as err:
            built.append(err)

    results = []
    try:
        with _smtp(cfg.smtp, cfg.timeout) as client:
            for item in built:
                if isinstance(item, ApiError):
                    results.append({'flag': False, 'msg': item.message})
                    continue
                msg, sender, recipients = item
                try:
                    client.send_message(msg, from_addr=sender, to_addrs=recipients)
                    results.append({'flag': True, 'msg': f'{sender}から[{",".join(recipients)}]へメールを送信しました。',
                                    'messageId': msg['Message-ID']})
                except smtplib.SMTPException as err:
                    log.warning('Send failed: %s', err)
                    results.append({'flag': False, 'msg': str(err)})
    except ApiError:
        raise
    except (OSError, smtplib.SMTPException) as err:
        log.error('SMTP connection failed: %s', err)
        raise ApiError(SMTP_CONNECT_FAILED, 502) from None
    return results


def _limit(value, maximum: int, default: int = 20) -> int:
    try:
        n = int(value) if value is not None else default
    except (TypeError, ValueError):
        raise ApiError('limit must be a number') from None
    return max(1, min(n, maximum))


def fetch_imap(cfg: Config, mailbox=None, limit=None, unseen=True) -> list:
    """Newest messages of a mailbox (unseen only by default). Messages are not marked as read."""
    server = cfg.imap
    _require(server, 'IMAP')
    n = _limit(limit, cfg.max_fetch)
    box = str(mailbox or cfg.imap_mailbox)
    try:
        if server.security == 'ssl':
            client = imaplib.IMAP4_SSL(server.host, server.port, ssl_context=ssl.create_default_context(),
                                       timeout=cfg.timeout)
        else:
            client = imaplib.IMAP4(server.host, server.port, timeout=cfg.timeout)
            if server.security == 'starttls':
                client.starttls(ssl_context=ssl.create_default_context())
        try:
            client.login(server.username, server.password)
            status, _ = client.select(f'"{box}"', readonly=True)
            if status != 'OK':
                raise ApiError(f'Mailbox not found: {box}', 404)
            status, data = client.uid('search', None, 'UNSEEN' if unseen else 'ALL')
            uids = data[0].split()[-n:] if status == 'OK' and data and data[0] else []
            result = []
            for uid in reversed(uids):
                status, parts = client.uid('fetch', uid, '(BODY.PEEK[])')
                raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None)
                if status == 'OK' and raw:
                    item = summarize(message_from_bytes(raw, policy=policy.default))
                    item['uid'] = uid.decode()
                    result.append(item)
            return result
        finally:
            try:
                client.logout()
            except (OSError, imaplib.IMAP4.error):
                pass
    except imaplib.IMAP4.error as err:
        log.warning('IMAP error: %s', err)
        raise ApiError('IMAP login or command failed', 502) from None
    except OSError as err:
        log.error('IMAP connection failed: %s', err)
        raise ApiError('Could not connect to the IMAP server', 502) from None


def fetch_pop3(cfg: Config, limit=None) -> list:
    """Newest messages on the POP3 server (left on the server)."""
    server = cfg.pop3
    _require(server, 'POP3')
    n = _limit(limit, cfg.max_fetch, 10)
    try:
        if server.security == 'ssl' or server.port in POP3_SSL_PORTS:
            client = poplib.POP3_SSL(server.host, server.port, timeout=cfg.timeout,
                                     context=ssl.create_default_context())
        else:
            client = poplib.POP3(server.host, server.port, timeout=cfg.timeout)
            try:
                offers_tls = 'STLS' in client.capa()
            except poplib.error_proto:
                offers_tls = False
            # STLS when offered (also with encryption "none"), required with "tls"
            if offers_tls or server.security == 'starttls':
                client.stls(context=ssl.create_default_context())
        try:
            client.user(server.username)
            client.pass_(server.password)
            count = client.stat()[0]
            result = []
            for i in range(count, max(count - n, 0), -1):
                lines = client.retr(i)[1]
                item = summarize(message_from_bytes(b'\r\n'.join(lines), policy=policy.default))
                item['number'] = i
                result.append(item)
            return result
        finally:
            try:
                client.quit()
            except (OSError, poplib.error_proto):
                pass
    except poplib.error_proto as err:
        log.warning('POP3 error: %s', err)
        raise ApiError(POP3_AUTH_FAILED, 502) from None
    except OSError as err:
        log.error('POP3 connection failed: %s', err)
        raise ApiError(POP3_CONNECT_FAILED, 502) from None

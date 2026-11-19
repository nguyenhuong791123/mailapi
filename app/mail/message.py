"""Builds a message from the `/send` request and parses received messages."""
import html
import mimetypes
import re
from email.headerregistry import Address
from email.message import EmailMessage, Message
from email.utils import formatdate, getaddresses, make_msgid, parseaddr
from html.parser import HTMLParser

from ..errors import ApiError
from ..files import decode_base64, make_zip, safe_filename

CHARSETS = ('utf-8', 'iso-2022-jp')
ADDRESS = re.compile(r'^[^@\s"(),:;<>\[\]\\]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$')


def addresses(value, field: str) -> list:
    """`"a@x, B <b@y>"` or a list of them -> validated address strings."""
    if value in (None, ''):
        return []
    items = value if isinstance(value, list) else [value]
    out = []
    for name, addr in getaddresses([str(v) for v in items]):
        if not addr:
            continue
        if not ADDRESS.match(addr):
            raise ApiError(f'Invalid address in {field}: {addr}')
        out.append(str(Address(display_name=name, addr_spec=addr)) if name else addr)
    return out


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(body: str) -> str:
    p = _Text()
    p.feed(body)
    return html.unescape(re.sub(r'\n{3,}', '\n\n', ''.join(p.parts))).strip()


def _truthy(v) -> bool:
    return v is True or str(v).lower() in ('true', '1', 'yes', 'on')


def build_message(mail: dict, max_recipients: int):
    """`(EmailMessage, sender, recipients)` for one entry of `mails`."""
    if not isinstance(mail, dict):
        raise ApiError('Each mail must be an object')
    senders = addresses(mail.get('from'), 'from')
    if len(senders) != 1:
        raise ApiError('from must be one address')
    to = addresses(mail.get('to'), 'to')
    cc = addresses(mail.get('cc'), 'cc')
    bcc = addresses(mail.get('bcc'), 'bcc')
    recipients = [parseaddr(a)[1] for a in to + cc + bcc]
    if not to:
        raise ApiError('to is required')
    if len(recipients) > max_recipients:
        raise ApiError(f'Too many recipients (max {max_recipients})')

    charset = str(mail.get('charset') or 'utf-8').lower()
    if charset not in CHARSETS:
        raise ApiError(f'charset must be one of {CHARSETS}')
    kind = str(mail.get('type') or 'plain').lower()
    body = str(mail.get('body') or '')

    msg = EmailMessage()
    # Line breaks would start a new header (header injection): a subject is one line.
    msg['Subject'] = re.sub(r'[\r\n]+', ' ', str(mail.get('subject') or ''))
    msg['From'] = senders[0]
    msg['To'] = ', '.join(to)
    if cc:
        msg['Cc'] = ', '.join(cc)
    # Bcc recipients are only in the envelope, never in the headers.
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=parseaddr(senders[0])[1].split('@')[-1])

    if kind == 'html':
        msg.set_content(html_to_text(body), charset=charset)
        msg.add_alternative(body, subtype='html', charset=charset)
    else:
        msg.set_content(body, charset=charset)

    files = []
    for f in mail.get('files') or []:
        if not isinstance(f, dict):
            raise ApiError('files must be a list of {filename, data}')
        name = safe_filename(f.get('filename'))
        files.append((name, decode_base64(f.get('data'), name)))

    if files and _truthy(mail.get('zip')):
        files = [('attachments.zip', make_zip(files, str(mail.get('zippw') or '')))]
    for name, data in files:
        ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

    return msg, parseaddr(senders[0])[1], recipients


def _decode(part: Message) -> str:
    payload = part.get_payload(decode=True) or b''
    for charset in (part.get_content_charset(), 'utf-8', 'iso-2022-jp', 'shift_jis'):
        if not charset:
            continue
        try:
            return payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode('utf-8', 'replace')


def summarize(msg: EmailMessage) -> dict:
    """Headers, text body (plain preferred over html) and attachment names of a received message."""
    out = {k.lower(): str(msg[k]) for k in ('From', 'To', 'Cc', 'Date', 'Subject', 'Message-ID') if msg[k]}
    plain, rich, attachments = None, None, []
    for part in msg.walk():
        if part.is_multipart():
            continue
        if part.get_content_disposition() == 'attachment' or part.get_filename():
            attachments.append({'filename': part.get_filename(), 'size': len(part.get_payload(decode=True) or b'')})
        elif part.get_content_type() == 'text/plain' and plain is None:
            plain = _decode(part)
        elif part.get_content_type() == 'text/html' and rich is None:
            rich = _decode(part)
    out['content'] = plain if plain is not None else (rich or '')
    out['attachments'] = attachments
    return out

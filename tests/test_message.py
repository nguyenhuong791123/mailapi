import base64
import io
import zipfile

import pytest
from email import message_from_bytes, policy

from app.errors import ApiError
from app.files import make_zip, safe_filename
from app.mail.message import build_message, summarize

PNG = base64.b64encode(b'\x89PNG fake').decode()


def mail(**kw):
    return {'from': 'Sender <sender@example.com>', 'to': 'a@example.com', 'subject': '件名', 'body': '本文', **kw}


def test_plain_mail_headers_and_recipients():
    msg, sender, rcpts = build_message(mail(cc='c@example.com', bcc='b@example.com'), 10)
    assert sender == 'sender@example.com'
    assert rcpts == ['a@example.com', 'c@example.com', 'b@example.com']
    assert msg['Cc'] == 'c@example.com'
    assert msg['Bcc'] is None                      # bcc only in the envelope
    assert msg['Subject'] == '件名'
    assert msg.get_body(('plain',)).get_content().strip() == '本文'


def test_html_mail_has_text_alternative():
    msg, _, _ = build_message(mail(type='html', body='<p>Hi<br>there &amp; you</p>'), 10)
    assert msg.get_body(('html',)).get_content().strip() == '<p>Hi<br>there &amp; you</p>'
    assert 'there & you' in msg.get_body(('plain',)).get_content()


def test_iso_2022_jp():
    msg, _, _ = build_message(mail(charset='iso-2022-jp'), 10)
    part = msg.get_body(('plain',))
    assert part.get_content_charset() == 'iso-2022-jp'
    assert part.get_content().strip() == '本文'


def test_attachment_without_files_is_sent():
    msg, _, _ = build_message(mail(), 10)            # the old code returned before sending
    assert list(msg.iter_attachments()) == []


def test_attachments_and_safe_names():
    msg, _, _ = build_message(mail(files=[{'filename': '../../etc/画像.png', 'data': PNG}]), 10)
    (att,) = list(msg.iter_attachments())
    assert att.get_filename() == '画像.png'
    assert att.get_content_type() == 'image/png'
    assert att.get_content() == b'\x89PNG fake'


def test_zip_with_password():
    files = [{'filename': 'a.txt', 'data': base64.b64encode(b'aaa').decode()},
             {'filename': 'a.txt', 'data': base64.b64encode(b'bbb').decode()}]
    msg, _, _ = build_message(mail(files=files, zip=True, zippw='pw1234'), 10)
    (att,) = list(msg.iter_attachments())
    assert att.get_filename() == 'attachments.zip'
    with zipfile.ZipFile(io.BytesIO(att.get_content())) as zf:
        assert sorted(zf.namelist()) == ['a (2).txt', 'a.txt']
        with pytest.raises(RuntimeError):
            zf.read('a.txt')                          # encrypted
        assert zf.read('a.txt', pwd=b'pw1234') == b'aaa'


def test_zip_without_password():
    data = make_zip([('x.txt', b'x')])
    assert zipfile.ZipFile(io.BytesIO(data)).read('x.txt') == b'x'


@pytest.mark.parametrize('bad', [
    {'to': 'not-an-address'}, {'to': ''}, {'from': 'a@x.com, b@x.com'}, {'charset': 'latin-1'},
    {'files': [{'filename': '..', 'data': PNG}]}, {'files': [{'filename': 'a', 'data': '***'}]},
    {'to': 'a@x.com, b@x.com, c@x.com, d@x.com'},
])
def test_invalid_mail(bad):
    with pytest.raises(ApiError):
        build_message(mail(**bad), 3)


def test_header_injection_is_not_possible():
    msg, _, _ = build_message(mail(subject='hi\r\nBcc: evil@example.com'), 10)
    assert msg['Bcc'] is None
    assert msg['Subject'] == 'hi Bcc: evil@example.com'


def test_safe_filename():
    assert safe_filename('C:\\temp\\a.pdf') == 'a.pdf'
    assert safe_filename('a\x00b.txt') == 'ab.txt'
    with pytest.raises(ApiError):
        safe_filename('dir/')


def test_summarize_prefers_plain_text():
    msg, _, _ = build_message(mail(type='html', body='<b>x</b>', files=[{'filename': 'f.png', 'data': PNG}]), 10)
    out = summarize(message_from_bytes(msg.as_bytes(), policy=policy.default))
    assert out['subject'] == '件名'
    assert out['content'].strip() == 'x'
    assert out['attachments'] == [{'filename': 'f.png', 'size': 9}]


def test_password_zip_keeps_japanese_names():
    data = make_zip([('成績表.csv', b'A,1')], 'pw')
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        (info,) = zf.infolist()
        assert info.filename == '成績表.csv' and info.flag_bits & 0x800
        assert zf.read('成績表.csv', pwd=b'pw') == b'A,1'

"""Any mail server: the connection is negotiated (SSL / STARTTLS / login) from what the server offers."""
from conftest import make_config, make_token
from app import create_app
from app.config import Server

AUTH = {'Authorization': f'Bearer {make_token()}'}
MAIL = {'mails': [{'from': 's@example.com', 'to': 'a@example.com', 'subject': 's', 'body': 'b'}]}


def send(server):
    return create_app(make_config(smtp=server)).test_client().post('/send', json=MAIL, headers=AUTH)


def test_gmail_with_encryption_none_uses_starttls(smtp):
    # smtp.gmail.com:587 offers AUTH only after STARTTLS (this failed with "SMTP AUTH extension not supported")
    res = send(Server('smtp.gmail.com', 587, 'none', 'me@gmail.com', 'app-password'))
    assert res.status_code == 200 and res.json['result'][0]['flag'] is True
    assert ('starttls',) in smtp.events and smtp.logins == ['me@gmail.com']


def test_plain_server_without_tls(smtp):
    smtp.extensions = {'auth'}                                 # e.g. a local test server
    res = send(Server('mailpit', 1025, 'none', 'dev', 'x'))
    assert res.status_code == 200 and ('starttls',) not in smtp.events and smtp.logins == ['dev']


def test_port_465_is_ssl_whatever_the_setting(smtp):
    res = send(Server('smtp.example.com', 465, 'starttls', 'u', 'p'))
    assert res.status_code == 200 and smtp.events[0] == ('connect', 'FakeSMTPSSL', 465)


def test_tls_required_but_not_offered(smtp):
    smtp.extensions = {'auth'}
    res = send(Server('smtp.example.com', 587, 'starttls', 'u', 'p'))
    assert (res.status_code, res.json['message']) == (502, 'MAIL_SMTP_NO_TLS')


def test_no_login_offered(smtp):
    smtp.extensions = set()
    res = send(Server('smtp.example.com', 25, 'none', 'u', 'p'))
    assert (res.status_code, res.json['message']) == (502, 'MAIL_SMTP_NO_AUTH')


def test_wrong_password(smtp):
    smtp.wrong_password = True
    res = send(Server('smtp.gmail.com', 587, 'starttls', 'me@gmail.com', 'normal-password'))
    assert (res.status_code, res.json['message']) == (502, 'MAIL_SMTP_AUTH_FAILED')
    assert smtp.sent == []


def test_no_account_sends_without_login(smtp):
    smtp.extensions = set()
    res = send(Server('relay.internal', 25, 'none', '', ''))
    assert res.status_code == 200 and smtp.logins == []

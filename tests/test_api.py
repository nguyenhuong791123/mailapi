import base64

from conftest import make_config, make_token
from app import create_app


def body(**kw):
    return {'mails': [{'from': 's@example.com', 'to': 'a@example.com', 'subject': 's', 'body': 'b', **kw}]}


def test_public_pages(client):
    assert client.get('/health').json == {'status': 'ok'}
    assert client.get('/').status_code == 200


def test_token_required(client, smtp):
    assert client.post('/send', json=body()).status_code == 401
    assert client.post('/send', json=body(), headers={'Authorization': 'Bearer nope'}).status_code == 401
    expired = make_token(exp=0)
    assert client.post('/send', json=body(), headers={'Authorization': f'Bearer {expired}'}).status_code == 401
    no_claims = make_token(uid=None)
    assert client.post('/send', json=body(), headers={'Authorization': f'Bearer {no_claims}'}).status_code == 401
    assert smtp.sent == []


def test_send(client, smtp, auth):
    res = client.post('/send', json=body(bcc='hidden@example.com'), headers=auth)
    assert res.status_code == 200
    (r,) = res.json['result']
    assert r['flag'] is True
    (msg, sender, rcpts) = smtp.sent[0]
    assert sender == 's@example.com' and rcpts == ['a@example.com', 'hidden@example.com']
    assert smtp.logins == ['user']


def test_auth_in_body_is_ignored(client, smtp, auth):
    payload = body()
    payload['auth'] = {'host': 'evil.example.com', 'username': 'x', 'password': 'y'}
    client.post('/send', json=payload, headers=auth)
    assert smtp.logins == ['user']                    # the configured account, not the request's


def test_invalid_mail_is_reported_and_others_sent(client, smtp, auth):
    payload = {'mails': [body()['mails'][0], {'from': 's@example.com', 'to': 'bad'}]}
    res = client.post('/send', json=payload, headers=auth).json['result']
    assert [r['flag'] for r in res] == [True, False]
    assert len(smtp.sent) == 1


def test_send_validation(client, auth):
    assert client.post('/send', json={}, headers=auth).status_code == 400
    assert client.post('/send', json={'mails': [{}] * 6}, headers=auth).status_code == 400


def test_unconfigured_servers(client, auth):
    assert client.post('/imap4', json={}, headers=auth).status_code == 503
    assert client.post('/pop3', json={}, headers=auth).status_code == 503


def test_auth_can_be_disabled(smtp):
    from app.config import AuthConfig
    app = create_app(make_config(auth=AuthConfig(False, '', '', '', ['RS256'], '', '')))
    assert app.test_client().post('/send', json=body()).status_code == 200


def test_body_too_large(auth):
    app = create_app(make_config(max_content_length=1024))
    data = base64.b64encode(b'x' * 4096).decode()
    res = app.test_client().post('/send', json=body(files=[{'filename': 'a', 'data': data}]), headers=auth)
    assert res.status_code == 413


def test_cors_only_for_configured_origins(auth):
    app = create_app(make_config(cors_origins=['http://localhost:1234']))
    c = app.test_client()
    ok = c.options('/send', headers={'Origin': 'http://localhost:1234', 'Access-Control-Request-Method': 'POST'})
    ng = c.options('/send', headers={'Origin': 'http://evil.example', 'Access-Control-Request-Method': 'POST'})
    assert ok.headers.get('Access-Control-Allow-Origin') == 'http://localhost:1234'
    assert 'Access-Control-Allow-Origin' not in ng.headers

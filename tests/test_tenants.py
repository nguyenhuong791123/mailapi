from conftest import make_config, make_token
from app import create_app
from app.config import Server
from app.tenants import TenantServers

EDU = {'tenant': 'edu',
       'smtp': {'host': 'smtp.edu', 'port': 1025, 'username': 'noreply@edu.example.com', 'password': 'pw', 'security': 'none'},
       'pop3': {'host': 'pop.edu', 'port': 1110, 'username': 'dev', 'password': 'pw2', 'security': 'ssl'}}


def tenant_app(fetch):
    app = create_app(make_config(settings_uri='http://be/internal/mail-servers', internal_secret='x' * 20))
    app.config['TENANTS'] = TenantServers(app.config['MAIL'], fetch=fetch)
    return app.test_client()


def test_accounts_of_the_tenant_are_used(smtp):
    calls = []
    client = tenant_app(lambda t: calls.append(t) or EDU)
    auth = {'Authorization': f'Bearer {make_token(client_id="edu")}'}
    res = client.post('/send', json={'mails': [{'to': 'a@example.com', 'subject': 's', 'body': 'b'}]}, headers=auth)
    assert res.status_code == 200 and res.json['result'][0]['flag'] is True
    (msg, sender, rcpts) = smtp.sent[0]
    assert sender == 'noreply@edu.example.com'          # default sender: the SMTP account
    assert smtp.logins == ['noreply@edu.example.com']   # not the environment's account ('user')
    client.post('/send', json={'mails': [{'from': 's@example.com', 'to': 'a@example.com', 'subject': 's', 'body': 'b'}]}, headers=auth)
    assert calls == ['edu']                             # cached


def test_tenant_without_mail_server(smtp):
    client = tenant_app(lambda t: {})
    auth = {'Authorization': f'Bearer {make_token(client_id="other")}'}
    res = client.post('/send', json={'mails': [{'from': 's@example.com', 'to': 'a@example.com', 'subject': 's', 'body': 'b'}]}, headers=auth)
    assert res.status_code == 503 and smtp.sent == []


def test_config_for_maps_servers():
    ts = TenantServers(make_config(settings_uri='http://be', settings_ttl=0), fetch=lambda t: EDU)
    cfg = ts.config_for('edu')
    assert cfg.smtp == Server('smtp.edu', 1025, 'none', 'noreply@edu.example.com', 'pw')
    assert cfg.pop3 == Server('pop.edu', 1110, 'ssl', 'dev', 'pw2')
    assert not cfg.imap.configured


def test_environment_accounts_without_settings_uri():
    cfg = make_config()
    assert TenantServers(cfg, fetch=lambda t: EDU).config_for('edu') is cfg


def test_each_tenant_has_its_own_server(smtp):
    servers = {'edu': EDU['smtp'], 'other': {**EDU['smtp'], 'host': 'smtp.other', 'username': 'info@other.example.com'}}
    client = tenant_app(lambda t: {'smtp': servers.get(t)})
    mail = {'mails': [{'to': 'a@example.com', 'subject': 's', 'body': 'b'}]}
    for t in ('edu', 'other'):
        assert client.post('/send', json=mail, headers={'Authorization': f'Bearer {make_token(client_id=t)}'}).status_code == 200
    assert smtp.logins == ['noreply@edu.example.com', 'info@other.example.com']
    assert [s[1] for s in smtp.sent] == ['noreply@edu.example.com', 'info@other.example.com']

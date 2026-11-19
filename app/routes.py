"""HTTP endpoints. Request bodies keep the original format; server accounts are never taken from them."""
import logging

from flask import Blueprint, current_app, g, jsonify, render_template, request

from .mail.client import fetch_imap, fetch_pop3, send_mails

log = logging.getLogger(__name__)
bp = Blueprint('mail', __name__)


def _config():
    """Mail accounts of the user's tenant (サーバー情報), or of the environment."""
    user = getattr(g, 'user', None) or {}
    return current_app.config['TENANTS'].config_for(user.get('tenant'))


def _body() -> dict:
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    if data.get('auth'):
        # The old API took the server account from the request; it now comes from the configuration.
        log.warning('Ignoring "auth" in the request body: mail servers are configured on the server')
    return data


@bp.get('/')
def index():
    return render_template('index.html')


@bp.get('/health')
def health():
    return jsonify({'status': 'ok'})


@bp.post('/send')
def send():
    """`{"mails": [{from, to, cc, bcc, subject, body, type: plain|html, charset, zip, zippw, files: [{filename, data}]}]}`"""
    body = _body()
    cfg = _config()
    mails = body.get('mails')
    # Sender: the SMTP account (an address) when the mail has none.
    if isinstance(mails, list) and '@' in cfg.smtp.username:
        for m in mails:
            if isinstance(m, dict) and not m.get('from'):
                m['from'] = cfg.smtp.username
    return jsonify({'result': send_mails(cfg, mails)})


@bp.post('/imap4')
def imap4():
    """`{"mailbox": "INBOX", "limit": 20, "unseen": true}` (all optional)"""
    body = _body()
    unseen = body.get('unseen', True) not in (False, 'false', 0, '0')
    return jsonify({'result': fetch_imap(_config(), body.get('mailbox'), body.get('limit'), unseen)})


@bp.post('/pop3')
def pop3():
    """`{"limit": 10}` (optional)"""
    body = _body()
    return jsonify({'result': fetch_pop3(_config(), body.get('limit'))})

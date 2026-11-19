"""Mail API: sends mail over SMTP and reads mail over IMAP / POP3."""
import logging
import os

from flask import Flask
from flask_cors import CORS

from .auth import init_auth
from .config import Config
from .errors import register_error_handlers
from .routes import bp
from .tenants import TenantServers

__version__ = '1.0.0'


def create_app(config: 'Config | None' = None) -> Flask:
    logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'),
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    cfg = config or Config.from_env()
    app = Flask(__name__)
    app.config['MAIL'] = cfg
    app.config['TENANTS'] = TenantServers(cfg)
    app.config['MAX_CONTENT_LENGTH'] = cfg.max_content_length
    app.config['VERSION'] = __version__
    # Only the configured origins may call the API from a browser (none when unset).
    if cfg.cors_origins:
        CORS(app, origins=cfg.cors_origins, allow_headers=['Authorization', 'Content-Type'])
    register_error_handlers(app)
    init_auth(app, cfg.auth)
    app.register_blueprint(bp)
    return app

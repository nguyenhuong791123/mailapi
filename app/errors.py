"""JSON error responses."""
import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    """An error returned to the client as `{"message": ...}` with the given status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return jsonify({'message': err.message}), err.status

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        return jsonify({'message': err.description}), err.code

    @app.errorhandler(Exception)
    def _unexpected(err: Exception):
        # Details stay in the log; the client only gets a generic message.
        log.exception('Unhandled error')
        return jsonify({'message': 'Internal server error'}), 500

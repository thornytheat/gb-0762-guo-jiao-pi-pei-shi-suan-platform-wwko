import os

from flask import Flask

from .errors import TrialError
from .routes import api
from .workbench import station


def create_app(archive=None):
    app = Flask(__name__)
    app.config.update(ARCHIVE=archive or os.getenv('PECTIN_ARCHIVE', 'instance/trials'), MAX_CONTENT_LENGTH=1_700_000)
    app.register_blueprint(api)
    app.register_blueprint(station)

    @app.errorhandler(TrialError)
    def invalid(error):
        return {'code': error.code}, error.status

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    return app

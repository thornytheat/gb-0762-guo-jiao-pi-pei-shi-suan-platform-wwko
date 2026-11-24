from flask import Blueprint, current_app, jsonify

from .input import from_request
from .modules.batches.service import preserve
from .modules.batches.storage import history, read
from .modules.certificate.service import issue
from .pipeline import process

api = Blueprint('trial_api', __name__, url_prefix='/api')


def preview(stage):
    return process(from_request(), stage)[stage]


@api.post('/assay')
def assay():
    return preview('assay')


@api.post('/dry')
def dry():
    return preview('dry')


@api.post('/formula')
def formula():
    return preview('formula')


@api.post('/blend')
def blend():
    return preview('blend')


@api.post('/stock')
def stock():
    return preview('stock')


@api.post('/batches')
def batches():
    record, fresh = preserve(current_app.config['ARCHIVE'], from_request())
    return {'batch_id': record['batch_id'], 'created': fresh, 'record': record}, 201 if fresh else 200


@api.get('/batches')
def list_batches():
    return {'batches': history(current_app.config['ARCHIVE'])}


@api.get('/batches/<identifier>')
def batch(identifier):
    return read(current_app.config['ARCHIVE'], identifier)


@api.get('/certificate/<identifier>')
def certificate(identifier):
    return issue(batch(identifier))


@api.get('/export/<identifier>')
def export(identifier):
    response = jsonify(certificate(identifier))
    response.headers['Content-Disposition'] = f'attachment; filename="pectin-{identifier[:12]}.json"'
    return response

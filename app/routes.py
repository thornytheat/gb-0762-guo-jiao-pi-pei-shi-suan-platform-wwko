from flask import Blueprint, current_app, jsonify, request

from .errors import TrialError
from .input import from_request
from .modules.batches.service import preserve
from .modules.batches.storage import history, read
from .modules.certificate.service import issue
from .modules.kiln import service as kiln
from .pipeline import process

api = Blueprint('trial_api', __name__, url_prefix='/api')


def preview(stage):
    return process(from_request(), stage)[stage]


def kiln_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise TrialError('JSON_REQUIRED', 400)
    return body


def pick(body, *keys):
    for key in keys:
        if body.get(key) is not None:
            return body[key]
    return None


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


# ---- 烘干炉台账：在烘暂扣、复称先配、分账对账、并发防超领、登记幂等 ----

@api.get('/kiln/batches')
def kiln_batches():
    return {'batches': kiln.list_batches(current_app.config['ARCHIVE'])}


@api.post('/kiln/batches')
def kiln_open_batch():
    body = kiln_body()
    root = current_app.config['ARCHIVE']
    result = kiln.open_batch(root, pick(body, 'batch', 'batch_id', 'lot', 'lot_id', 'id'),
                             pick(body, 'stock_g', 'stock', 'total_g', 'stock_grams'),
                             pick(body, 'moisture_pct', 'moisture', 'moisture_in_pct', 'in_moisture_pct'))
    view = kiln.inspect_batch(root, result['batch_id'])
    envelope = {'created': result['created'], 'batch_id': result['batch_id'],
                'view': view, 'detail': view, 'record': view, **view}
    return jsonify(envelope), 201 if result['created'] else 200


@api.post('/kiln/demo')
def kiln_demo():
    view = kiln.seed_demo(current_app.config['ARCHIVE'])
    return jsonify({'created': True, 'batch_id': view['batch_id'], 'view': view,
                    'detail': view, 'record': view, **view}), 201


@api.get('/kiln/batches/<identifier>')
def kiln_batch(identifier):
    view = kiln.inspect_batch(current_app.config['ARCHIVE'], identifier)
    return jsonify({'batch_id': identifier, 'view': view, 'detail': view, 'record': view, **view})


@api.post('/kiln/loads')
def kiln_charge():
    body = kiln_body()
    result = kiln.send_to_dryer(current_app.config['ARCHIVE'],
                                pick(body, 'batch', 'batch_id', 'lot', 'lot_id'),
                                pick(body, 'charged_g', 'charge_g', 'grams', 'amount_g', 'sent_g'),
                                pick(body, 'load', 'load_id', 'furnace', 'furnace_id', 'kiln'))
    return jsonify(result), 201 if result['created'] else 200


@api.post('/kiln/loads/<identifier>/register')
def kiln_register(identifier):
    body = kiln_body()
    result = kiln.register_output(current_app.config['ARCHIVE'], identifier,
                                  pick(body, 'weighed_g', 'weight_g', 'output_g', 'actual_g', 'grams',
                                       'reweighed_g', 'actual_weight_g'),
                                  pick(body, 'moisture_pct', 'moisture', 'moisture_out_pct',
                                       'measured_moisture_pct', 'out_moisture_pct', 'measured_moisture'),
                                  pick(body, 'tolerance_bp', 'max_loss_bp', 'dry_loss_tolerance_bp'))
    return jsonify(result), 201 if result['created'] else 200


@api.post('/kiln/requisitions')
def kiln_requisition():
    body = kiln_body()
    result = kiln.create_requisition(current_app.config['ARCHIVE'],
                                     pick(body, 'batch', 'batch_id', 'lot', 'lot_id'),
                                     pick(body, 'amount_g', 'grams', 'qty_g', 'need_g', 'requested_g'),
                                     pick(body, 'req', 'req_id', 'requisition', 'order',
                                          'idempotency_key', 'key'),
                                     pick(body, 'load', 'load_id', 'furnace', 'furnace_id', 'kiln'))
    return jsonify(result), 201 if result['created'] else 200

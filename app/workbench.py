import json

from flask import Blueprint, abort, current_app, render_template, request

from .config import REVISION
from .errors import TrialError
from .input import load
from .modules.batches.service import preserve
from .modules.batches.storage import history, read
from .modules.certificate.service import issue
from .modules.kiln import service as kiln
from .pipeline import process
from .stages import LABELS, PLAN_FIELDS, STAGES

station = Blueprint('station', __name__)


def materials(mode):
    if mode != 'custom':
        return load(mode)
    try:
        proposal = json.loads(request.form.get('proposal', '{}'))
    except ValueError:
        raise TrialError('BAD_PROPOSAL_JSON') from None
    return {'assays': request.form.get('assays', ''), 'plan': {key: request.form.get(key, '') for key in PLAN_FIELDS},
            'proposal': proposal}


@station.route('/', methods=['GET', 'POST'])
@station.route('/trial/<stage>', methods=['GET', 'POST'])
def review(stage='stock'):
    if stage not in LABELS:
        abort(404)
    mode = request.values.get('sample', 'dirty')
    data, pack, error, record, entries, fresh = {}, None, None, None, [], False
    root = current_app.config['ARCHIVE']
    source = {}
    try:
        source = materials(mode)
        if stage in ('batches', 'certificate'):
            if stage == 'batches' and request.method == 'POST':
                record, fresh = preserve(root, source)
            entries = history(root)
            if stage == 'certificate' and (entries or request.args.get('batch')):
                pack = issue(read(root, request.args.get('batch') or entries[0]['batch_id']))
        else:
            data = process(source, stage)
    except TrialError as exc:
        error = exc.code
    form_plan = request.form if mode == 'custom' else source.get('plan', {})
    form_assays = request.form.get('assays', '') if mode == 'custom' else source.get('assays', '')
    form_proposal = request.form.get('proposal', '{}') if mode == 'custom' else json.dumps(source.get('proposal', {}))
    kiln_rows = kiln.list_batches(root) if stage == 'stock' else []
    return render_template('station.html', stages=STAGES, labels=LABELS, fields=PLAN_FIELDS,
                           revision=REVISION, stage=stage, mode=mode, data=data, error=error,
                           form_plan=form_plan, form_assays=form_assays, form_proposal=form_proposal,
                           record=record, fresh=fresh, entries=entries, pack=pack, kiln_rows=kiln_rows)


@station.route('/kiln', methods=['GET', 'POST'])
@station.route('/trial/kiln', methods=['GET', 'POST'])
def kiln_board():
    root = current_app.config['ARCHIVE']
    fault, notice, created, notice_meta = None, None, None, {}
    selected = request.values.get('batch') or None

    if request.method == 'POST':
        action = request.form.get('action', '')
        selected = request.form.get('batch') or selected
        try:
            if action == 'seed':
                kiln.seed_demo(root)
                selected, notice, created = kiln.DEMO_BATCH, 'seed', True
            elif action == 'open':
                result = kiln.open_batch(root, request.form.get('batch'), request.form.get('stock_g'),
                                         request.form.get('moisture_pct'))
                selected, notice, created = result['batch_id'], 'open', result['created']
            elif action == 'charge':
                result = kiln.send_to_dryer(root, request.form.get('batch'), request.form.get('charged_g'),
                                           request.form.get('load'))
                selected, notice, created = result['item']['batch'], 'charge', result['created']
            elif action == 'register':
                result = kiln.register_output(root, request.form.get('load'), request.form.get('weighed_g'),
                                             request.form.get('moisture_pct'), request.form.get('tolerance_bp'))
                selected, notice, created = result['batch'], 'register', result['created']
                notice_meta = {'status': result['status'], 'released_g': result['released_g']}
            elif action == 'draw':
                result = kiln.create_requisition(root, request.form.get('batch'), request.form.get('amount_g'),
                                                 request.form.get('req'), request.form.get('load'))
                selected, notice, created = result['batch'], 'draw', result['created']
            else:
                raise TrialError('UNKNOWN_ACTION', 400)
        except TrialError as exc:
            fault = {'code': exc.code, **exc.detail}

    batches = kiln.list_batches(root)
    if not selected and batches:
        selected = batches[0]['batch']
    view = None
    if selected:
        try:
            view = kiln.inspect_batch(root, selected)
        except TrialError as exc:
            fault = fault or {'code': exc.code, **exc.detail}
            view = None
    return render_template('kiln.html', stages=STAGES, labels=LABELS, revision=REVISION,
                           batches=batches, view=view, selected=selected, fault=fault,
                           notice=notice, created=created, notice_meta=notice_meta, form=request.form)

import json

from flask import Blueprint, abort, current_app, render_template, request

from .config import REVISION
from .errors import TrialError
from .input import load
from .modules.batches.service import preserve
from .modules.batches.storage import history, read
from .modules.certificate.service import issue
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
    return render_template('station.html', stages=STAGES, labels=LABELS, fields=PLAN_FIELDS,
                           revision=REVISION, stage=stage, mode=mode, data=data, error=error,
                           form_plan=form_plan, form_assays=form_assays, form_proposal=form_proposal,
                           record=record, fresh=fresh, entries=entries, pack=pack)

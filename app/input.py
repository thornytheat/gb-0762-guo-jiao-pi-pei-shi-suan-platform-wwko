import json
from flask import request

from .config import DATA
from .errors import TrialError


def load(mode):
    if mode not in ('dirty', 'clean'):
        raise TrialError('UNKNOWN_SAMPLE', 404)
    directory = DATA / mode
    return {'assays': (directory / 'assays.csv').read_text(encoding='utf-8'),
            **json.loads((directory / 'trial.json').read_text(encoding='utf-8'))}


def from_request():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise TrialError('JSON_REQUIRED', 400)
    if 'sample' in body:
        materials = load(body['sample'])
        if set(body) - {'sample', 'plan', 'proposal'}:
            raise TrialError('UNKNOWN_REQUEST_FIELD', 400)
        return {**materials, **{k: v for k, v in body.items() if k != 'sample'}}
    if set(body) - {'assays', 'plan', 'proposal'} or not isinstance(body.get('assays'), str):
        raise TrialError('ASSAYS_REQUIRED', 400)
    return body

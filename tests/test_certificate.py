import hashlib
import json


def proof(client, payload):
    batch = client.post('/api/batches', json=payload).json['batch_id']
    return client.get('/api/certificate/' + batch).json


def test_dirty_certifies_new_allocation(client):
    r = proof(client, {'sample':'dirty'})
    assert r['can_trial'] and (r['isolation_lines'], r['stock_lines']) == (7, 7)
    assert r['record']['stages']['formula']['can_make'] is False


def test_quality_failure_prevents_signature(client, dirty):
    dirty['plan'].update(gel_low_sag=195, gel_high_sag=200)
    r = proof(client, dirty)
    assert not r['can_trial'] and r['record']['stages']['stock']['shortage_g'] == 10000


def test_digest_is_independently_recomputable(client):
    r = proof(client, {'sample':'dirty'})
    raw = json.dumps(r['record'], sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    assert hashlib.sha256(raw).hexdigest() == r['integrity_sha256']


def test_download_is_content_addressed(client):
    r = proof(client, {'sample':'clean'})
    reply = client.get('/api/export/' + r['batch_id'])
    assert reply.json == r and reply.headers['Content-Disposition'].startswith('attachment;')


def test_export_contains_recompute_parameters(client):
    r = proof(client, {'sample':'dirty'})
    assert r['record']['parameters']['plan']['step_g'] == 2500
    assert 'PJ-06' in r['record']['stages']['assay']['isolated'][0]['raw']


def test_missing_export_remains_404(client):
    assert client.get('/api/export/nope').status_code == 404

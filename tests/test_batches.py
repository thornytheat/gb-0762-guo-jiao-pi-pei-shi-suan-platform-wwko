from concurrent.futures import ThreadPoolExecutor

from app.main import create_app
from app.modules.batches.service import preserve


def test_replay_same_snapshot(client):
    one = client.post('/api/batches', json={'sample':'dirty'})
    two = client.post('/api/batches', json={'sample':'dirty'})
    assert (one.status_code, two.status_code, two.json['created']) == (201, 200, False)
    assert one.json['record'] == two.json['record']
    assert len(client.get('/api/batches').json['batches']) == 1


def test_failed_calculation_publishes_nothing(client):
    response = client.post('/api/batches', json={'sample':'dirty', 'plan':{}})
    assert (response.status_code, response.json['code']) == (422, 'PLAN_FIELDS_REQUIRED')
    assert client.get('/api/batches').json['batches'] == []


def test_concurrent_publication_single_archive(tmp_path, dirty):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: preserve(tmp_path, dirty), range(7)))
    assert sum(new for _, new in results) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_query_works_after_new_application(tmp_path):
    first = create_app(tmp_path).test_client().post('/api/batches', json={'sample':'dirty'}).json
    later = create_app(tmp_path).test_client().get('/api/batches/' + first['batch_id'])
    assert later.json == first['record']


def test_plan_changes_archive_identity(client, dirty):
    first = client.post('/api/batches', json={'sample':'dirty'}).json['batch_id']
    dirty['plan']['dry_min_g'] += 1
    second = client.post('/api/batches', json=dirty).json['batch_id']
    assert first != second


def test_unknown_batch_rejected(client):
    response = client.get('/api/batches/missing')
    assert (response.status_code, response.json) == (404, {'code':'BATCH_NOT_FOUND'})

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.errors import TrialError
from app.main import create_app
from app.modules.kiln import service as kiln


@pytest.fixture
def root(tmp_path):
    return tmp_path / 'archive'


@pytest.fixture
def scenario(root):
    """题面情景：30000 g 同批果胶分两炉各 10000 g，余料 10000 g。"""
    kiln.open_batch(root, 'PJ-01', 30000, '20')
    kiln.send_to_dryer(root, 'PJ-01', 10000, load='F1')
    kiln.send_to_dryer(root, 'PJ-01', 10000, load='F2')
    return root


def expect_error(fn, code):
    with pytest.raises(TrialError) as info:
        fn()
    assert info.value.code == code
    return info.value


# ---- 可领口径：在烘暂扣、余料可领、预计出炉量不计入 ----

def test_only_un_sent_remainder_is_available_while_furnaces_drying(scenario):
    view = kiln.inspect_batch(scenario, 'PJ-01')
    assert (view['remainder_g'], view['available_g'], view['withheld_g']) == (10000, 10000, 20000)
    assert [lot['availability_code'] for lot in view['loads']] == ['IN_DRYER', 'IN_DRYER']
    assert all(lot['available_g'] == 0 for lot in view['loads'])


def test_drying_expected_output_is_never_booked(scenario):
    # 即使“预计”每炉出 8000 g，试算可领仍只有余料 10000 g：预计量不进库存。
    view = kiln.inspect_batch(scenario, 'PJ-01')
    assert view['available_g'] == view['remainder_g'] == 10000
    error = expect_error(lambda: kiln.create_requisition(scenario, 'PJ-01', 10001, req='R0'), 'KILN_SHORTAGE')
    assert error.detail['available_g'] == 10000


def test_remainder_can_be_issued_as_usual(scenario):
    result = kiln.create_requisition(scenario, 'PJ-01', 10000, req='R-REM')
    assert [line['source'] for line in result['lines']] == ['REMAINDER']
    view = kiln.inspect_batch(scenario, 'PJ-01')
    assert view['remainder_g'] == view['available_g'] == 0


def test_charge_cannot_exceed_remainder(root):
    kiln.open_batch(root, 'PJ', 5000, '10')
    error = expect_error(lambda: kiln.send_to_dryer(root, 'PJ', 6000, load='F1'), 'KILN_REMAINDER_SHORT')
    assert error.detail['short_g'] == 1000
    assert kiln.inspect_batch(root, 'PJ')['remainder_g'] == 5000


# ---- 已复称部分先配 ----

def test_weighed_furnace_becomes_available_and_allocates_first(scenario):
    registered = kiln.register_output(scenario, 'F1', 8030, '0.50')
    assert registered['status'] == 'WEIGHED' and registered['released_g'] == 8030
    view = kiln.inspect_batch(scenario, 'PJ-01')
    assert (view['available_g'], view['withheld_g']) == (18030, 10000)

    draw = kiln.create_requisition(scenario, 'PJ-01', 9000, req='R1')
    assert [(line['source'], line['grams']) for line in draw['lines']] == [('F1', 8030), ('REMAINDER', 970)]


def test_specified_furnace_draw_never_touches_other_sources(scenario):
    kiln.register_output(scenario, 'F1', 8000, '0')
    draw = kiln.create_requisition(scenario, 'PJ-01', 4000, req='R1', load='F1')
    assert draw['lines'] == [{'source': 'F1', 'load': 'F1', 'grams': 4000}]
    view = kiln.inspect_batch(scenario, 'PJ-01')
    assert view['remainder_g'] == 10000  # 指定炉次不动余料


# ---- 出炉登记幂等：已被领用后重试不重复计入可领 ----

def test_register_retry_after_issue_does_not_double_count(scenario):
    kiln.register_output(scenario, 'F1', 8030, '0.50')
    kiln.create_requisition(scenario, 'PJ-01', 4000, req='R1', load='F1')
    before = kiln.inspect_batch(scenario, 'PJ-01')

    retry = kiln.register_output(scenario, 'F1', 8030, '0.50')
    assert (retry['created'], retry['released_g']) == (False, 0)

    after = kiln.inspect_batch(scenario, 'PJ-01')
    assert after['available_g'] == before['available_g'] == 14030
    f1 = next(lot for lot in after['loads'] if lot['load'] == 'F1')
    assert (f1['drawn_g'], f1['available_g']) == (4000, 4030)


def test_register_conflicting_measurement_is_rejected(scenario):
    kiln.register_output(scenario, 'F1', 8030, '0.50')
    expect_error(lambda: kiln.register_output(scenario, 'F1', 8031, '0.50'), 'KILN_LOAD_CONFLICT')


def test_charge_replay_does_not_double_decrement_remainder(root):
    kiln.open_batch(root, 'PJ', 10000, '10')
    first = kiln.send_to_dryer(root, 'PJ', 4000, load='F1')
    second = kiln.send_to_dryer(root, 'PJ', 4000, load='F1')
    assert (first['created'], second['created']) == (True, False)
    assert kiln.inspect_batch(root, 'PJ')['remainder_g'] == 6000


def test_requisition_replay_does_not_double_issue(scenario):
    kiln.register_output(scenario, 'F1', 8000, '0')
    first = kiln.create_requisition(scenario, 'PJ-01', 3000, req='DUP', load='F1')
    second = kiln.create_requisition(scenario, 'PJ-01', 3000, req='DUP', load='F1')
    assert (first['created'], second['created']) == (True, False)
    view = kiln.inspect_batch(scenario, 'PJ-01')
    assert next(l for l in view['loads'] if l['load'] == 'F1')['drawn_g'] == 3000
    assert len(view['requisitions']) == 1


# ---- 并发：两张单同时提交也不能领超同一炉 ----

def test_two_simultaneous_orders_cannot_overdraw_one_furnace(root):
    kiln.open_batch(root, 'B', 10000, '10')
    kiln.send_to_dryer(root, 'B', 10000, load='F1')
    kiln.register_output(root, 'F1', 9000, '0')

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(
            lambda i: _safe_draw(root, f'O{i}', 5000), ('A', 'B')))
    assert sorted(outcomes) == ['KILN_SHORTAGE', 'ok']
    f1 = kiln.inspect_batch(root, 'B')['loads'][0]
    assert f1['drawn_g'] == 5000 and f1['available_g'] == 4000


def test_many_concurrent_orders_fill_exactly_to_furnace_cap(root):
    kiln.open_batch(root, 'B', 10000, '10')
    kiln.send_to_dryer(root, 'B', 10000, load='F1')
    kiln.register_output(root, 'F1', 9000, '0')

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda i: _safe_draw(root, f'Q{i}', 3000), range(8)))
    assert outcomes.count('ok') == 3 and outcomes.count('KILN_SHORTAGE') == 5
    f1 = kiln.inspect_batch(root, 'B')['loads'][0]
    assert f1['drawn_g'] == 9000 and f1['available_g'] == 0


def test_same_requisition_key_racing_concurrently_creates_once(root):
    kiln.open_batch(root, 'B', 10000, '10')
    kiln.send_to_dryer(root, 'B', 10000, load='F1')
    kiln.register_output(root, 'F1', 9000, '0')
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: kiln.create_requisition(root, 'B', 4000, req='SAME', load='F1'), range(6)))
    assert sum(1 for r in results if r['created']) == 1
    assert kiln.inspect_batch(root, 'B')['loads'][0]['drawn_g'] == 4000


def _safe_draw(root, req, amount):
    try:
        kiln.create_requisition(root, 'B', amount, req=req, load='F1')
        return 'ok'
    except TrialError as exc:
        return exc.code


# ---- 水分蒸发与干物损耗分别对账，对不上暂停签发 ----

def test_exact_conservation_reconciles_both_ledgers(root):
    kiln.open_batch(root, 'B', 10000, '10')
    kiln.send_to_dryer(root, 'B', 10000, load='F1')
    result = kiln.register_output(root, 'F1', 9000, '0')
    assert result['status'] == 'WEIGHED'
    assert result['reconcile']['balanced'] and result['reconcile']['codes'] == []
    assert result['reconcile']['water']['evaporated_g'] == '1000.0000'
    assert result['reconcile']['dry']['loss_g'] == '0.0000'


def test_water_and_dry_ledgers_flag_different_failures(root):
    kiln.open_batch(root, 'W', 10000, '10')
    kiln.send_to_dryer(root, 'W', 10000, load='FW')
    gain = kiln.register_output(root, 'FW', 11000, '10')
    assert gain['status'] == 'HOLD'
    assert gain['reconcile']['water']['ok'] is False
    assert gain['reconcile']['water']['code'] == 'WATER_GAIN'
    assert gain['reconcile']['dry']['code'] == 'DRY_GAIN'

    kiln.open_batch(root, 'D', 10000, '10')
    kiln.send_to_dryer(root, 'D', 10000, load='FD')
    loss = kiln.register_output(root, 'FD', 8500, '5')
    assert loss['status'] == 'HOLD'
    assert loss['reconcile']['water']['ok'] is True
    assert loss['reconcile']['dry']['ok'] is False
    assert loss['reconcile']['dry']['code'] == 'DRY_LOSS_OVER_TOLERANCE'
    # 放大容忍度后，同样的实测数在另一炉可以签发
    kiln.open_batch(root, 'D2', 10000, '10')
    kiln.send_to_dryer(root, 'D2', 10000, load='FD2')
    ok = kiln.register_output(root, 'FD2', 8500, '5', tolerance_bp=2000)
    assert ok['status'] == 'WEIGHED'


def test_failed_reconciliation_withholds_output_and_blocks_issue(scenario):
    bad = kiln.register_output(scenario, 'F2', 11000, '10')
    assert bad['status'] == 'HOLD' and bad['released_g'] == 0
    view = kiln.inspect_batch(scenario, 'PJ-01')
    f2 = next(lot for lot in view['loads'] if lot['load'] == 'F2')
    assert (f2['available_g'], f2['withheld_g'], f2['issuance']) == (0, 11000, 'PAUSED')
    assert f2['availability_code'] == 'RECONCILE_FAILED'
    expect_error(lambda: kiln.create_requisition(scenario, 'PJ-01', 1, load='F2'), 'KILN_LOAD_NOT_ISSUABLE')
    # 不指定炉次的单也不会碰到 HOLD 炉，只能领余料
    draw = kiln.create_requisition(scenario, 'PJ-01', 10000, req='R-OK')
    assert [line['source'] for line in draw['lines']] == ['REMAINDER']


# ---- 建批幂等/冲突与输入校验 ----

def test_open_batch_idempotent_and_conflict(root):
    assert kiln.open_batch(root, 'PJ', 10000, '20')['created'] is True
    assert kiln.open_batch(root, 'PJ', 10000, '20')['created'] is False
    error = expect_error(lambda: kiln.open_batch(root, 'PJ', 10000, '21'), 'KILN_BATCH_CONFLICT')
    assert error.status == 409


@pytest.mark.parametrize('field,kwargs', [
    ('stock_g', dict(batch='PJ', stock_g=0, moisture_pct='20')),
    ('stock_g', dict(batch='PJ', stock_g=-5, moisture_pct='20')),
    ('moisture_pct', dict(batch='PJ', stock_g=100, moisture_pct='120')),
    ('batch', dict(batch='bad/id', stock_g=100, moisture_pct='20')),
])
def test_invalid_open_values_rejected(root, field, kwargs):
    error = expect_error(lambda: kiln.open_batch(root, **kwargs), 'KILN_BAD_ID' if field == 'batch' else 'KILN_BAD_VALUE')
    assert error.detail.get('field') == field or error.code == 'KILN_BAD_ID'


def test_unknown_batch_and_load_are_404(root):
    expect_error(lambda: kiln.inspect_batch(root, 'NOPE'), 'KILN_BATCH_NOT_FOUND')
    kiln.open_batch(root, 'PJ', 100, '10')
    expect_error(lambda: kiln.register_output(root, 'GHOST', 90, '0'), 'KILN_LOAD_NOT_FOUND')


# ---- JSON API ----

def test_api_full_kiln_flow(client):
    opened = client.post('/api/kiln/batches', json={'batch': 'PJ-9', 'stock_g': 20000, 'moisture_pct': '20'})
    assert opened.status_code == 201 and opened.json['batch_id'] == 'PJ-9'
    charged = client.post('/api/kiln/loads', json={'batch': 'PJ-9', 'charged_g': 10000, 'load': 'F1'})
    assert charged.status_code == 201
    reply = client.post('/api/kiln/loads/F1/register', json={'weighed_g': 8030, 'moisture_pct': '0.50'})
    assert reply.status_code == 201 and reply.json['status'] == 'WEIGHED'

    view = client.get('/api/kiln/batches/PJ-9')
    assert view.status_code == 200
    assert (view.json['available_g'], view.json['withheld_g']) == (18030, 0)

    drawn = client.post('/api/kiln/requisitions', json={'batch': 'PJ-9', 'amount_g': 5000, 'req': 'A1'})
    assert drawn.status_code == 201
    again = client.post('/api/kiln/requisitions', json={'batch': 'PJ-9', 'amount_g': 5000, 'req': 'A1'})
    assert again.status_code == 200 and again.json['created'] is False
    assert client.get('/api/kiln/batches/missing').status_code == 404


def test_api_shortage_returns_available_and_short(client):
    client.post('/api/kiln/batches', json={'batch': 'PJ', 'stock_g': 1000, 'moisture_pct': '10'})
    reply = client.post('/api/kiln/requisitions', json={'batch': 'PJ', 'amount_g': 2000})
    assert reply.status_code == 422 and reply.json['code'] == 'KILN_SHORTAGE'
    assert reply.json['available_g'] == 1000 and reply.json['short_g'] == 1000


def test_concurrent_http_requisitions_never_overdraw(tmp_path):
    archive = tmp_path / 'archive'
    app = create_app(archive)
    bootstrap = app.test_client()
    bootstrap.post('/api/kiln/batches', json={'batch': 'B', 'stock_g': 10000, 'moisture_pct': '10'})
    bootstrap.post('/api/kiln/loads', json={'batch': 'B', 'charged_g': 10000, 'load': 'F1'})
    bootstrap.post('/api/kiln/loads/F1/register', json={'weighed_g': 9000, 'moisture_pct': '0'})

    def fire(index):
        worker = app.test_client()
        return worker.post('/api/kiln/requisitions',
                           json={'batch': 'B', 'amount_g': 5000, 'req': f'H{index}', 'load': 'F1'}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(fire, (1, 2)))
    assert sorted(codes) == [201, 422]
    view = app.test_client().get('/api/kiln/batches/B').json
    assert view['loads'][0]['drawn_g'] == 5000


# ---- 试算页面 ----

def test_kiln_page_shows_what_is_available_and_why_withheld(client):
    client.post('/api/kiln/demo')
    page = client.get('/kiln?batch=' + kiln.DEMO_BATCH)
    assert page.status_code == 200
    html = page.data.decode()
    for phrase in ('可领', '暂扣', '在烘', '未送烘', '已复称', '暂停签发',
                   '水分蒸发', '干物损耗', '预计出炉量不计入'):
        assert phrase in html
    assert '18030' in html and 'DEMO-F1' in html and 'DEMO-F2' in html


def test_trial_kiln_alias_and_nav_link(client):
    assert client.get('/trial/kiln').status_code == 200
    home = client.get('/').data.decode()
    assert '/kiln' in home and '烘干试算' in home


def test_stock_page_summarises_kiln_after_demo(client):
    client.post('/api/kiln/demo')
    html = client.get('/trial/stock').data.decode()
    assert 'kiln-availability' in html and kiln.DEMO_BATCH in html


def test_kiln_form_actions_render_feedback(client):
    response = client.post('/kiln', data={'action': 'open', 'batch': 'PJ-FORM', 'stock_g': '12000',
                                          'moisture_pct': '18'})
    assert response.status_code == 200 and 'PJ-FORM'.encode() in response.data
    response = client.post('/kiln', data={'action': 'seed'})
    assert response.status_code == 200 and '题面情景'.encode() in response.data
    response = client.post('/kiln', data={'action': 'draw', 'batch': kiln.DEMO_BATCH, 'amount_g': '1'})
    assert response.status_code == 200 and '领料单已签发'.encode() in response.data


def test_kiln_form_failed_reconciliation_shows_paused_notice(client):
    client.post('/api/kiln/demo')
    response = client.post('/kiln', data={'action': 'register', 'batch': kiln.DEMO_BATCH, 'load': 'DEMO-F2',
                                          'weighed_g': '11000', 'moisture_pct': '10'})
    assert response.status_code == 200
    html = response.data.decode()
    assert '对不上' in html and '暂停签发' in html
    f2 = next(line for line in client.get('/api/kiln/batches/' + kiln.DEMO_BATCH).json['loads']
              if line['load'] == 'DEMO-F2')
    assert (f2['status'], f2['available_g'], f2['issuance']) == ('HOLD', 0, 'PAUSED')


def test_kiln_form_validation_fault_is_reported(client):
    response = client.post('/kiln', data={'action': 'open', 'batch': 'a/b', 'stock_g': '1',
                                          'moisture_pct': '1'})
    assert response.status_code == 200 and b'KILN_BAD_ID' in response.data

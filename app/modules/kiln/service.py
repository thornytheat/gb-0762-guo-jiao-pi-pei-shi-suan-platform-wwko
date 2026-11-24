import json
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.errors import TrialError
from app.modules.assay.units import scaled
from . import store
from .reconcile import DEFAULT_DRY_LOSS_MAX_BP, reconcile

ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
DEMO_BATCH = 'PJ-KILN-DEMO'

# 可领/暂扣原因码与页面文案的对照由模板渲染；这里固定码值。
REASON_AVAILABLE = 'WEIGHED'
REASON_REMAINDER = 'REMAINDER'
REASON_DRYING = 'IN_DRYER'
REASON_RECONCILE = 'RECONCILE_FAILED'


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _ident(value, field):
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not ID_RE.fullmatch(value.strip()):
        raise TrialError('KILN_BAD_ID', field=field)
    return value.strip()


def _opt_ident(value, field):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _ident(value, field)


def _grams(value, field):
    try:
        amount = scaled(str(value), 1, 10_000_000)
    except (ValueError, TypeError):
        raise TrialError('KILN_BAD_VALUE', field=field) from None
    if amount <= 0:
        raise TrialError('KILN_BAD_VALUE', field=field)
    return amount


def _moisture_bp(value, field='moisture_pct'):
    try:
        return scaled(str(value), 100, 9999)
    except (ValueError, TypeError):
        raise TrialError('KILN_BAD_VALUE', field=field) from None


def _tolerance_bp(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_DRY_LOSS_MAX_BP
    try:
        amount = scaled(str(value), 1, 10_000)
    except (ValueError, TypeError):
        raise TrialError('KILN_BAD_VALUE', field='tolerance_bp') from None
    return amount


def pct_text(bp):
    return f'{(Decimal(bp) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}%'


def _load_view(row):
    status = row['status']
    weighed = row['weighed_g']
    drawn = row['drawn_g']
    ledger = json.loads(row['ledger_json']) if row['ledger_json'] else None
    if status == 'WEIGHED':
        available_g, withheld_g = weighed - drawn, 0
        code, issuance, expected = REASON_AVAILABLE, 'RELEASED', None
    elif status == 'HOLD':
        available_g, withheld_g = 0, max((weighed or 0) - drawn, 0)
        code, issuance = REASON_RECONCILE, 'PAUSED'
        expected = None
    else:
        available_g, withheld_g = 0, row['charged_g']
        code, issuance, expected = REASON_DRYING, 'PENDING', 'EXPECTED_OUTPUT_NOT_BOOKED'
    return {'load': row['load'], 'load_id': row['load'], 'seq': row['seq'], 'batch': row['batch'],
            'charged_g': row['charged_g'], 'moisture_in_bp': row['moisture_in_bp'],
            'moisture_in_pct': pct_text(row['moisture_in_bp']), 'status': status,
            'weighed_g': weighed, 'moisture_out_bp': row['moisture_out_bp'],
            'moisture_out_pct': pct_text(row['moisture_out_bp']) if row['moisture_out_bp'] is not None else None,
            'drawn_g': drawn, 'available_g': available_g, 'withheld_g': withheld_g,
            'availability_code': code, 'issuance': issuance, 'reason_code': expected,
            'reconcile_codes': ledger['codes'] if ledger else [], 'reconcile': ledger,
            'registered_at': row['registered_at']}


def open_batch(root, batch, stock_g, moisture_pct):
    batch = _ident(batch, 'batch')
    stock = _grams(stock_g, 'stock_g')
    moisture_bp = _moisture_bp(moisture_pct)
    with store.transaction(root) as conn:
        row = conn.execute('SELECT * FROM kiln_batches WHERE batch=?', (batch,)).fetchone()
        if row is not None:
            if row['stock_g'] != stock or row['moisture_bp'] != moisture_bp:
                raise TrialError('KILN_BATCH_CONFLICT', 409)
            return {'created': False, 'batch': batch, 'batch_id': batch}
        conn.execute('INSERT INTO kiln_batches (batch, stock_g, moisture_bp, remainder_g, created_at) VALUES (?,?,?,?,?)',
                     (batch, stock, moisture_bp, stock, _now()))
    return {'created': True, 'batch': batch, 'batch_id': batch}


def send_to_dryer(root, batch, charged_g, load=None):
    batch = _ident(batch, 'batch')
    charged = _grams(charged_g, 'charged_g')
    wanted = _opt_ident(load, 'load')
    with store.transaction(root) as conn:
        b = conn.execute('SELECT * FROM kiln_batches WHERE batch=?', (batch,)).fetchone()
        if b is None:
            raise TrialError('KILN_BATCH_NOT_FOUND', 404)
        if wanted is not None:
            existing = conn.execute('SELECT * FROM kiln_loads WHERE load=?', (wanted,)).fetchone()
            if existing is not None:
                if existing['batch'] != batch or existing['charged_g'] != charged:
                    raise TrialError('KILN_LOAD_CONFLICT', 409)
                return {'created': False, 'load': wanted, 'load_id': wanted, 'item': _load_view(existing)}
        if charged > b['remainder_g']:
            raise TrialError('KILN_REMAINDER_SHORT', 422, remainder_g=b['remainder_g'],
                             need_g=charged, short_g=charged - b['remainder_g'])
        seq = conn.execute('SELECT COALESCE(MAX(seq), 0) + 1 AS s FROM kiln_loads WHERE batch=?',
                           (batch,)).fetchone()['s']
        load_id = wanted or f'{batch}-F{seq:02d}'
        try:
            conn.execute("""INSERT INTO kiln_loads
                            (load, batch, seq, charged_g, moisture_in_bp, status, drawn_g, created_at)
                            VALUES (?,?,?,?,?, 'DRYING', 0, ?)""",
                         (load_id, batch, seq, charged, b['moisture_bp'], _now()))
        except sqlite3.IntegrityError:
            raise TrialError('KILN_LOAD_CONFLICT', 409) from None
        conn.execute('UPDATE kiln_batches SET remainder_g = remainder_g - ? WHERE batch=?', (charged, batch))
        row = conn.execute('SELECT * FROM kiln_loads WHERE load=?', (load_id,)).fetchone()
        return {'created': True, 'load': load_id, 'load_id': load_id, 'item': _load_view(row)}


# 车间用语别名
charge = send_to_dryer


def register_output(root, load, weighed_g, moisture_pct, tolerance_bp=None, **_ignored):
    load_id = _ident(load, 'load')
    weighed = _grams(weighed_g, 'weighed_g')
    moisture_out_bp = _moisture_bp(moisture_pct, 'moisture_pct')
    max_loss_bp = _tolerance_bp(tolerance_bp)
    with store.transaction(root) as conn:
        row = conn.execute('SELECT * FROM kiln_loads WHERE load=?', (load_id,)).fetchone()
        if row is None:
            raise TrialError('KILN_LOAD_NOT_FOUND', 404)
        if row['status'] != 'DRYING':
            # 幂等重试：出炉已登记过。即使中间已经被领用，也原样返回，
            # 绝不把复称量再次加进可领库存。
            if row['weighed_g'] != weighed or row['moisture_out_bp'] != moisture_out_bp:
                raise TrialError('KILN_LOAD_CONFLICT', 409)
            view = _load_view(row)
            return {'created': False, 'replayed': True, 'load': load_id, 'load_id': load_id,
                    'batch': row['batch'], 'status': row['status'], 'released_g': 0,
                    'increment_g': 0, 'reconcile': view['reconcile'], 'item': view}
        ledger = reconcile(row['charged_g'], row['moisture_in_bp'], weighed, moisture_out_bp, max_loss_bp)
        status = 'WEIGHED' if ledger['balanced'] else 'HOLD'
        conn.execute("""UPDATE kiln_loads
                        SET status=?, weighed_g=?, moisture_out_bp=?, ledger_json=?, registered_at=?
                        WHERE load=? AND status='DRYING'""",
                     (status, weighed, moisture_out_bp, json.dumps(ledger, ensure_ascii=False), _now(), load_id))
        row = conn.execute('SELECT * FROM kiln_loads WHERE load=?', (load_id,)).fetchone()
        view = _load_view(row)
        released = weighed if status == 'WEIGHED' else 0
        return {'created': True, 'replayed': False, 'load': load_id, 'load_id': load_id,
                'batch': row['batch'], 'status': status, 'released_g': released,
                'increment_g': released, 'reconcile': ledger, 'item': view}


def create_requisition(root, batch, amount_g, req=None, load=None):
    batch = _ident(batch, 'batch')
    amount = _grams(amount_g, 'amount_g')
    req_id = _opt_ident(req, 'req') or uuid4().hex
    only_load = _opt_ident(load, 'load')
    with store.transaction(root) as conn:
        old = conn.execute('SELECT * FROM kiln_requisitions WHERE req=?', (req_id,)).fetchone()
        if old is not None:
            if old['batch'] != batch or old['amount_g'] != amount or (old['load_ref'] or None) != only_load:
                raise TrialError('KILN_REQ_CONFLICT', 409)
            line_rows = conn.execute('SELECT source, load, grams FROM kiln_req_lines WHERE req=? ORDER BY rowid',
                                     (req_id,)).fetchall()
            lines = [{'source': r['source'], 'load': r['load'], 'grams': r['grams']} for r in line_rows]
            return {'created': False, 'replayed': True, 'req': req_id, 'req_id': req_id, 'batch': batch,
                    'amount_g': amount, 'load': only_load, 'lines': lines, 'issued_g': amount}

        b = conn.execute('SELECT * FROM kiln_batches WHERE batch=?', (batch,)).fetchone()
        if b is None:
            raise TrialError('KILN_BATCH_NOT_FOUND', 404)

        if only_load is not None:
            target = conn.execute('SELECT * FROM kiln_loads WHERE load=?', (only_load,)).fetchone()
            if target is None or target['batch'] != batch:
                raise TrialError('KILN_LOAD_NOT_FOUND', 404)
            if target['status'] != 'WEIGHED':
                error = TrialError('KILN_LOAD_NOT_ISSUABLE', 422, load=only_load,
                                   availability_code=_load_view(target)['availability_code'])
                error.detail['status'] = target['status']
                raise error
            sources = [(only_load, target['weighed_g'] - target['drawn_g'], only_load)]
        else:
            rows = conn.execute("SELECT * FROM kiln_loads WHERE batch=? AND status='WEIGHED' ORDER BY seq",
                                (batch,)).fetchall()
            # 已复称的炉次先配，按炉次顺序；复称炉次配完再动未送烘余料。
            sources = [(r['load'], r['weighed_g'] - r['drawn_g'], r['load']) for r in rows]
            sources.append((REASON_REMAINDER, b['remainder_g'], None))

        available = sum(cap for _, cap, _ in sources if cap > 0)
        if available < amount:
            raise TrialError('KILN_SHORTAGE', 422, batch=batch, need_g=amount,
                             available_g=available, short_g=amount - available)

        left, plan = amount, []
        for source, cap, ref in sources:
            if cap <= 0 or left == 0:
                continue
            take = min(left, cap)
            plan.append((source, take, ref))
            left -= take

        for source, take, ref in plan:
            if source == REASON_REMAINDER:
                cur = conn.execute('UPDATE kiln_batches SET remainder_g = remainder_g - ? WHERE batch=? AND remainder_g >= ?',
                                   (take, batch, take))
            else:
                cur = conn.execute("""UPDATE kiln_loads SET drawn_g = drawn_g + ?
                                      WHERE load=? AND status='WEIGHED' AND weighed_g - drawn_g >= ?""",
                                   (take, source, take))
            if cur.rowcount != 1:
                # 条件更新未命中说明余量已被并发事务改掉；IMMEDIATE 串行下不应发生，发生即拒发。
                raise TrialError('KILN_CONCURRENT_CHANGE', 409)

        conn.execute('INSERT INTO kiln_requisitions (req, batch, amount_g, load_ref, created_at) VALUES (?,?,?,?,?)',
                     (req_id, batch, amount, only_load, _now()))
        for source, take, ref in plan:
            conn.execute('INSERT INTO kiln_req_lines (req, batch, source, load, grams) VALUES (?,?,?,?,?)',
                         (req_id, batch, source, ref, take))
        return {'created': True, 'replayed': False, 'req': req_id, 'req_id': req_id, 'batch': batch,
                'amount_g': amount, 'load': only_load,
                'lines': [{'source': s, 'load': r, 'grams': t} for s, t, r in plan], 'issued_g': amount}


# 车间动作别名
draw = create_requisition
issue = create_requisition


def inspect_batch(root, batch):
    batch = _ident(batch, 'batch')
    with store.reader(root) as conn:
        b = conn.execute('SELECT * FROM kiln_batches WHERE batch=?', (batch,)).fetchone()
        if b is None:
            raise TrialError('KILN_BATCH_NOT_FOUND', 404)
        rows = conn.execute('SELECT * FROM kiln_loads WHERE batch=? ORDER BY seq', (batch,)).fetchall()
        req_rows = conn.execute("""SELECT * FROM kiln_requisitions WHERE batch=?
                                   ORDER BY created_at DESC, rowid DESC LIMIT 20""", (batch,)).fetchall()
        requisitions = []
        for r in req_rows:
            line_rows = conn.execute('SELECT source, load, grams FROM kiln_req_lines WHERE req=? ORDER BY rowid',
                                     (r['req'],)).fetchall()
            requisitions.append({'req': r['req'], 'amount_g': r['amount_g'], 'load': r['load_ref'],
                                 'created_at': r['created_at'],
                                 'lines': [{'source': x['source'], 'load': x['load'], 'grams': x['grams']}
                                           for x in line_rows]})

    loads = [_load_view(r) for r in rows]
    remainder = b['remainder_g']
    load_available = sum(l['available_g'] for l in loads)
    available_g = remainder + load_available
    withheld_g = sum(l['withheld_g'] for l in loads)
    drawn_g = sum(l['drawn_g'] for l in loads)
    sources = [{'source': l['load'], 'kind': 'LOAD', 'seq': l['seq'], 'code': REASON_AVAILABLE,
                'available_g': l['available_g']}
               for l in loads if l['status'] == 'WEIGHED']
    sources.append({'source': REASON_REMAINDER, 'kind': REASON_REMAINDER, 'seq': None,
                    'code': REASON_REMAINDER, 'available_g': remainder})
    return {'batch': batch, 'batch_id': batch, 'stock_g': b['stock_g'], 'moisture_bp': b['moisture_bp'],
            'moisture_pct': pct_text(b['moisture_bp']), 'remainder_g': remainder,
            'available_g': available_g, 'withheld_g': withheld_g, 'drawn_g': drawn_g,
            'charged_g': sum(l['charged_g'] for l in loads),
            'weighed_g': sum(l['weighed_g'] or 0 for l in loads),
            'load_available_g': load_available, 'sources': sources, 'loads': loads,
            'requisitions': requisitions}


# 试算页面/台账别名
trial = inspect_batch
board = inspect_batch
status = inspect_batch


def list_batches(root):
    if not store.exists(root):
        return []
    with store.reader(root) as conn:
        rows = conn.execute("""
            SELECT b.batch, b.stock_g, b.moisture_bp, b.remainder_g, b.created_at,
                   COALESCE(SUM(CASE WHEN l.status='WEIGHED' THEN l.weighed_g - l.drawn_g ELSE 0 END), 0) AS load_available_g,
                   COALESCE(SUM(CASE WHEN l.status='DRYING' THEN l.charged_g
                                     WHEN l.status='HOLD' THEN l.weighed_g - l.drawn_g ELSE 0 END), 0) AS withheld_g,
                   COALESCE(SUM(l.drawn_g), 0) AS drawn_g,
                   COUNT(l.load) AS load_count
            FROM kiln_batches b LEFT JOIN kiln_loads l ON l.batch = b.batch
            GROUP BY b.batch
            ORDER BY b.created_at DESC, b.batch
        """).fetchall()
    result = []
    for r in rows:
        result.append({'batch': r['batch'], 'batch_id': r['batch'], 'stock_g': r['stock_g'],
                       'moisture_bp': r['moisture_bp'], 'moisture_pct': pct_text(r['moisture_bp']),
                       'remainder_g': r['remainder_g'], 'load_available_g': r['load_available_g'],
                       'available_g': r['remainder_g'] + r['load_available_g'],
                       'withheld_g': r['withheld_g'], 'drawn_g': r['drawn_g'], 'load_count': r['load_count'],
                       'created_at': r['created_at']})
    return result


def seed_demo(root):
    """铺陈题面情景：同批 30000 g 分两炉，首炉已复称对账相符，次炉在烘，余料 10000 g 未送烘。"""
    open_batch(root, DEMO_BATCH, 30000, '20')
    send_to_dryer(root, DEMO_BATCH, 10000, load='DEMO-F1')
    send_to_dryer(root, DEMO_BATCH, 10000, load='DEMO-F2')
    register_output(root, 'DEMO-F1', 8030, '0.50')
    return inspect_batch(root, DEMO_BATCH)

from collections import Counter, defaultdict

from app.reasons import read_text
from .reader import records
from .units import day, grams, scaled


def parse(raw):
    row = {key: read_text(value) for key, value in raw.items()}
    return {"lot": row['lot'], "expires": day(row['expires']), "stock_g": grams(row['stock'], row['unit']),
            "moisture_bp": scaled(row['moisture_pct'], 100, 9999), "gel_msag": scaled(row['gel_sag'], 1000, 500_000)}


def receive(text):
    issues, groups, meta = [], defaultdict(list), Counter()

    def isolate(code, line, fields):
        issues.append({'code': code, 'line': line, 'raw': fields})

    for line, fields, reason, raw in records(text):
        meta['input'] += 1
        if reason in {'REPEATED_HEADER', 'BLANK_ROW'}:
            meta[reason] += 1
            continue
        if reason:
            isolate(reason, line, fields)
            continue
        try:
            lot = parse(raw)
        except ValueError as exc:
            isolate(str(exc), line, fields)
            continue
        groups[lot['lot']].append((lot, line, fields))
    lots = []
    for group in groups.values():
        first, *repeats = group
        if any(row[0] != first[0] for row in repeats):
            for _, line, fields in group:
                isolate('ASSAY_CONFLICT', line, fields)
            continue
        lots.append({**first[0], 'line': first[1], 'raw': first[2]})
        for _, line, fields in repeats:
            isolate('EXACT_DUPLICATE', line, fields)
    issues.sort(key=lambda row: row['line'])
    counts = {'input': meta['input'], 'blanks': meta['BLANK_ROW'], 'sections': meta['REPEATED_HEADER'] + 1,
              'accepted': len(lots), 'isolated': len(issues)}
    return {'lots': sorted(lots, key=lambda lot: lot['lot']), 'isolated': issues, 'counts': counts,
            'state': 'HEADER_ONLY' if not (lots or issues) else 'PROCESSED',
            'balanced': counts['input'] == counts['blanks'] + counts['sections'] - 1 + len(lots) + len(issues),
            'reason_counts': dict(Counter(issue['code'] for issue in issues))}

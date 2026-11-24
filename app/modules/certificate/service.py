from app.modules.batches.seal import canonical, sha


def issue(record):
    stages = record['stages']
    stock = stages['stock']
    blend = stages['blend']
    return {'batch_id': record['batch_id'], 'integrity_sha256': sha(canonical(record)),
            'can_trial': blend['status'] == 'FEASIBLE' and stock['balanced'] and stock['shortage_g'] == 0,
            'stock_lines': len(stock['rows']), 'isolation_lines': len(stages['assay']['isolated']), 'record': record}

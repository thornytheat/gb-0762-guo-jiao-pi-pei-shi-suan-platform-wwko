from .weights import as_grams, dry_units


def convert(lots, as_of):
    converted = []
    for lot in sorted(lots, key=lambda row: (row['expires'], row['lot'])):
        dry = dry_units(lot['stock_g'], lot['moisture_bp'])
        status = 'EXPIRED' if lot['expires'] < as_of else 'ELIGIBLE' if lot['stock_g'] else 'NO_STOCK'
        converted.append({**lot, 'dry_stock_u': dry, 'dry_stock_g': as_grams(dry), 'status': status})
    return {'lots': converted, 'as_of': as_of,
            'eligible_dry_g': as_grams(sum(row['dry_stock_u'] for row in converted if row['status'] == 'ELIGIBLE'))}

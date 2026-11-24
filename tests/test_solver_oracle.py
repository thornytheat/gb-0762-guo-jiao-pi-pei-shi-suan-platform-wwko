from itertools import product

from app.modules.blend.search import search


def test_pruning_agrees_with_small_exhaustive_oracle():
    lots = [{'stock_g': 3, 'moisture_bp': 1000, 'gel_msag': 100},
            {'stock_g': 2, 'moisture_bp': 0, 'gel_msag': 230},
            {'stock_g': 3, 'moisture_bp': 2000, 'gel_msag': 140},
            {'stock_g': 2, 'moisture_bp': 3000, 'gel_msag': 175}]
    for low in (100, 140, 150, 160, 190, 240):
        plan = dict(step_g=1, target_g=5, dry_min_u=40000, gel_low_sag=low, gel_high_sag=low+20)
        possible = []
        for draw in product(*(range(lot['stock_g']+1) for lot in lots)):
            dry = sum(n*(10000-lot['moisture_bp']) for n,lot in zip(draw,lots))
            gel = sum(n*(10000-lot['moisture_bp'])*lot['gel_msag'] for n,lot in zip(draw,lots))
            if sum(draw) == 5 and dry >= 40000 and low*dry <= gel <= (low+20)*dry:
                possible.append(draw)
        expected = min(possible, key=lambda draw: (sum(x > 0 for x in draw), tuple(-x for x in draw))) if possible else None
        actual, _ = search(lots, plan)
        assert actual == (list(expected) if expected else None)

from app.modules.dry.weights import as_grams, dry_units, sag_display


def weigh(lots, allocation):
    dry = moment = 0
    for lot, grams in zip(lots, allocation):
        amount = dry_units(grams, lot['moisture_bp'])
        dry += amount
        moment += amount * lot['gel_msag']
    return dry, moment


def quality(plan, mass, dry, moment):
    return {'mass': mass == plan['target_g'], 'dry': dry >= plan['dry_min_u'],
            'gel_low': bool(dry and moment >= dry * plan['gel_low_sag']),
            'gel_high': bool(dry and moment <= dry * plan['gel_high_sag'])}


def measurements(dry, moment):
    return {'dry_g': as_grams(dry), 'gel_sag': sag_display(moment, dry), 'dry_u': dry, 'gel_moment': str(moment)}

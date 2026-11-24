from app.modules.dry.weights import as_grams

SCALE = 10_000
# 干物损耗容忍上限：占入炉干物的万分之五十，即 0.5%。
# 精确守恒（损耗为 0）在任何容忍度下都对账相符。
DEFAULT_DRY_LOSS_MAX_BP = 50


def reconcile(charged_g, moisture_in_bp, weighed_g, moisture_out_bp, max_loss_bp=DEFAULT_DRY_LOSS_MAX_BP):
    """按万分克整数分别结清水账与干物账。

    水账：入炉水 - 出炉水 = 水分蒸发，蒸发量不允许为负。
    干物账：入炉干物 - 出炉干物 = 干物损耗；损耗不允许为负（干物凭空增加），
    且不得超过入炉干物的约定比例。两项独立判定、分别给出原因码。
    """
    water_in_u = charged_g * moisture_in_bp
    dry_in_u = charged_g * (SCALE - moisture_in_bp)
    water_out_u = weighed_g * moisture_out_bp
    dry_out_u = weighed_g * (SCALE - moisture_out_bp)

    evaporated_u = water_in_u - water_out_u
    dry_loss_u = dry_in_u - dry_out_u

    water_ok = evaporated_u >= 0
    if not water_ok:
        water_code = 'WATER_GAIN'
    elif water_in_u == water_out_u and charged_g and weighed_g:
        water_code = 'WATER_NO_EVAPORATION'
    else:
        water_code = 'OK'

    if dry_loss_u < 0:
        dry_ok, dry_code = False, 'DRY_GAIN'
    elif dry_in_u and dry_loss_u * SCALE > dry_in_u * max_loss_bp:
        dry_ok, dry_code = False, 'DRY_LOSS_OVER_TOLERANCE'
    else:
        dry_ok, dry_code = True, 'OK'

    loss_bp_text = None
    if dry_in_u:
        from decimal import Decimal, ROUND_HALF_UP
        loss_bp_text = str((Decimal(dry_loss_u) * SCALE / dry_in_u).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    water = {'in_u': water_in_u, 'out_u': water_out_u, 'delta_u': evaporated_u,
             'in_g': as_grams(water_in_u), 'out_g': as_grams(water_out_u),
             'evaporated_g': as_grams(evaporated_u), 'ok': water_ok, 'code': water_code}
    dry = {'in_u': dry_in_u, 'out_u': dry_out_u, 'loss_u': dry_loss_u, 'loss_bp': loss_bp_text,
           'max_loss_bp': max_loss_bp, 'in_g': as_grams(dry_in_u), 'out_g': as_grams(dry_out_u),
           'loss_g': as_grams(dry_loss_u), 'ok': dry_ok, 'code': dry_code}
    codes = [code for code in (water_code, dry_code) if code != 'OK']
    return {'balanced': water_ok and dry_ok, 'codes': codes, 'water': water, 'dry': dry}

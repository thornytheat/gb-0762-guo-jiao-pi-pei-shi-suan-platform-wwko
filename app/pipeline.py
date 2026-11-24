from .errors import TrialError
from .modules.assay.service import receive
from .modules.dry.service import convert
from .modules.formula.contract import normalize
from .modules.formula.service import inspect
from .modules.blend.service import select
from .modules.stock.balance import reconcile


def process(material, stage='archive'):
    if len(material['assays']) > 250_000:
        raise TrialError('ASSAYS_TOO_LARGE', 413)
    assays = receive(material['assays'])
    result = {'assay': assays}
    if stage == 'assay':
        return result
    plan = normalize(material.get('plan'))
    result['dry'] = convert(assays['lots'], plan['as_of'])
    lots = result['dry']['lots']
    result['plan'] = plan
    if stage == 'dry':
        return result
    if stage in ('formula', 'archive'):
        result['formula'] = inspect(plan, lots, material.get('proposal', {}))
    if stage == 'formula':
        return result
    result['blend'] = select(plan, lots)
    if stage == 'blend':
        return result
    result['stock'] = reconcile(plan, lots, result['blend'])
    return result

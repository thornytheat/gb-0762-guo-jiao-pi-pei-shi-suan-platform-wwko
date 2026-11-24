import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter

from app.config import REVISION


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(material, results, start):
    assay_digest = sha(material['assays'].encode())
    settings = {'plan': material['plan'], 'proposal': material.get('proposal', {})}
    handle = sha(canonical([REVISION, assay_digest, settings]))
    return {'batch_id': handle, 'rule': REVISION, 'assay_sha256': assay_digest, 'parameters': settings,
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'elapsed_ms': round((perf_counter() - start)*1000), 'stages': results}

import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.errors import TrialError
from .seal import canonical


def read(root, identifier):
    if not re.fullmatch('[a-f0-9]{64}', identifier):
        raise TrialError('BATCH_NOT_FOUND', 404)
    try:
        return json.loads((Path(root) / f'{identifier}.json').read_bytes())
    except FileNotFoundError:
        raise TrialError('BATCH_NOT_FOUND', 404) from None


def write(root, record):
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    identifier = record['batch_id']
    target = directory / f'{identifier}.json'
    with NamedTemporaryFile(dir=directory, delete=False) as file:
        temp = Path(file.name)
        try:
            file.write(canonical(record))
            file.flush()
            os.fsync(file.fileno())
            try:
                os.link(temp, target)
            except FileExistsError:
                return read(root, identifier), False
            return record, True
        finally:
            temp.unlink(missing_ok=True)


def history(root):
    paths = sorted(Path(root).glob('*.json'), key=lambda path: path.stat().st_mtime_ns, reverse=True)[:50]
    return [{key: record[key] for key in ('batch_id', 'rule', 'created_at', 'elapsed_ms')}
            for record in (read(root, path.stem) for path in paths)]

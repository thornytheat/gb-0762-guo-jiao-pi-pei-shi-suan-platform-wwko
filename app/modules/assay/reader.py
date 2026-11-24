import csv
from io import StringIO

from app.errors import TrialError

COLUMNS = ('lot', 'expires', 'stock', 'unit', 'moisture_pct', 'gel_sag')


def records(text):
    text = text.removeprefix('\ufeff')
    if not text:
        raise TrialError('EMPTY_FILE')
    reader = csv.reader(StringIO(text, newline=''), strict=True)
    header = None
    try:
        while True:
            line = reader.line_num + 1
            fields = next(reader, None)
            if fields is None:
                if header is None:
                    raise TrialError('BLANK_FILE')
                return
            if not any(field.strip() for field in fields):
                if header is not None:
                    yield line, fields, 'BLANK_ROW', None
                continue
            if header is None:
                header = [field.strip() for field in fields]
                if sorted(header) != sorted(COLUMNS):
                    raise TrialError('BAD_HEADER')
                continue
            if fields == header:
                yield line, fields, 'REPEATED_HEADER', None
            elif len(fields) != len(header):
                yield line, fields, 'COLUMN_COUNT', None
            else:
                yield line, fields, None, dict(zip(header, fields))
    except csv.Error:
        raise TrialError('CSV_SYNTAX') from None

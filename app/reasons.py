SENTINELS = frozenset({'N/A', 'NULL', '-', '未知'})


def read_text(value):
    text = value.strip()
    if not text:
        raise ValueError('EMPTY_CELL')
    if text in SENTINELS:
        raise ValueError('MISSING_SENTINEL')
    return text

from time import perf_counter

from app.pipeline import process
from .seal import manifest
from .storage import write


def preserve(root, material):
    started = perf_counter()
    results = process(material)
    return write(root, manifest(material, results, started))

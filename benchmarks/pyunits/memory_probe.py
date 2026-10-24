"""Measure extra peak resident memory when attaching units in a fresh process."""

import argparse
import gc
import json
import resource
import sys

import numpy as np

from benchmark_config import DEFAULT_CONFIG, source_settings


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("library", choices=("snt", "pint", "unyt", "astropy"))
parser.add_argument("input_kind", choices=("scalar", "list", "ndarray"))
parser.add_argument("elements", type=int)
parser.add_argument("--config", default=DEFAULT_CONFIG)
parser.add_argument("--input-start", type=float, required=True)
parser.add_argument("--input-stop", type=float, required=True)
args = parser.parse_args()
if args.elements < 1:
    parser.error("elements must be positive")

source_mode, local_repo = source_settings(args.config)
if source_mode == "local":
    sys.path.insert(0, str(local_repo / "build" / "python"))

raw = np.linspace(args.input_start, args.input_stop, args.elements, dtype=np.float64)
source = float(raw[0]) if args.input_kind == "scalar" else raw.tolist() if args.input_kind == "list" else raw

if args.library == "snt":
    from scinumtools3.puq import Quantity
    warmup = lambda: Quantity(0.0, "m")
    make = lambda: Quantity(source, "m")
elif args.library == "pint":
    import pint
    ureg = pint.UnitRegistry()
    warmup = lambda: ureg.Quantity(0.0, "m")
    make = lambda: ureg.Quantity(source, "m")
elif args.library == "unyt":
    import unyt as uy
    warmup = lambda: uy.unyt_quantity(0.0, "m")
    make = (lambda: uy.unyt_quantity(source, "m")) if args.input_kind == "scalar" else (lambda: uy.unyt_array(source, "m"))
else:
    import astropy.units as au
    warmup = lambda: au.Quantity(0.0, au.m)
    make = lambda: au.Quantity(source, au.m)

warmup()
gc.collect()
scale = 1 if sys.platform == "darwin" else 1024  # ru_maxrss is bytes on macOS, KiB on Linux.
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
quantity = make()
after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
if quantity is None:
    raise AssertionError("Construction returned no quantity")
print(json.dumps({"peak_rss_before_bytes": before, "peak_rss_after_bytes": after,
                  "peak_rss_delta_bytes": max(0, after - before)}))

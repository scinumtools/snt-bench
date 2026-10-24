"""Read bootstrap strings from the DIPL file before importing SNT3."""

import ast
import os
from pathlib import Path
import re


DEFAULT_CONFIG = Path(__file__).with_name("config.dip")


def literal_string(source, path):
    """Read a literal DIPL string at a dotted path without evaluating the file."""
    parents = []
    for line in source.splitlines():
        match = re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?', line)
        if not match:
            continue
        indent, name, value = match.groups()
        depth = len(indent)
        while parents and parents[-1][0] >= depth:
            parents.pop()
        qualified = '.'.join([node for _, node in parents] + [name])
        if value is not None:
            if qualified == path:
                return ast.literal_eval(value)
        else:
            parents.append((depth, name))
    raise ValueError(f"DIP configuration requires a literal {path} string")


def pinned_snt_version(config_path=DEFAULT_CONFIG):
    """Return the SNT3 pin from the chosen DIP configuration."""
    return literal_string(Path(config_path).read_text(), "pyunits.packages.snt.version")


def source_settings(config_path=DEFAULT_CONFIG):
    """Resolve source choice and checkout path before importing SNT3."""
    text = Path(config_path).read_text()
    source = os.environ.get("SNT_SOURCE") or literal_string(text, "pyunits.execution.target.source")
    source = "pypi" if source == "pinned" else source
    if source not in ("pypi", "local"):
        raise ValueError(f"unknown SNT3 source: {source}")
    repo = Path(os.environ.get("SNT_LOCAL_REPO") or
                literal_string(text, "pyunits.execution.paths.local_repo"))
    if not repo.is_absolute():
        repo = (DEFAULT_CONFIG.parents[2] / repo).resolve()
    return source, repo


def as_list(value):
    return value if isinstance(value, list) else [value]

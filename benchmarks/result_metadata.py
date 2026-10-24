"""Portable, non-identifying system and path labels for benchmark outputs."""

import platform
import csv
import json
from pathlib import Path
import re


def platform_label():
    """Return OS family and CPU architecture without host or OS build details."""
    system = "macOS" if platform.system() == "Darwin" else platform.system()
    return f"{system}-{platform.machine()}"


def path_label(value, repository):
    """Make paths relative where possible and hide unrelated absolute paths."""
    path = Path(value)
    if not path.is_absolute():
        return str(value)
    repository = Path(repository).resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(repository).as_posix()
    except ValueError:
        try:
            return "../" + resolved.relative_to(repository.parent).as_posix()
        except ValueError:
            pass
        parts = resolved.parts
        if "site-packages" in parts:
            index = parts.index("site-packages")
            return Path(*parts[index:]).as_posix()
        return path.name


def command_labels(command, repository):
    """Return command arguments with absolute paths made portable."""
    return [path_label(item, repository) if Path(item).is_absolute() else item
            for item in command]


def strip_pyperf_host_details(path):
    """Remove pyperf metadata that identifies a host or local installation."""
    path = Path(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    private_keys = {"hostname", "boot_time", "python_executable", "python_config_args"}

    def clean(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key in private_keys or key == "uptime":
                    continue
                if key == "platform":
                    result[key] = platform_label()
                else:
                    result[key] = clean(item)
            return result
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    path.write_text(json.dumps(clean(document), separators=(",", ":")) + "\n", encoding="utf-8")


def sanitize_result_metadata(results_dir, repository):
    """Remove host-identifying details while retaining reproducible context."""
    results_dir = Path(results_dir)
    repository = Path(repository).resolve()
    for path in results_dir.iterdir():
        if not path.is_file():
            continue
        if path.name.endswith(".pyperf.json"):
            strip_pyperf_host_details(path)
        elif path.suffix == ".json":
            document = json.loads(path.read_text(encoding="utf-8"))

            def clean_paths(value):
                if isinstance(value, dict):
                    return {key: (platform_label() if key == "platform" else clean_paths(item))
                            for key, item in value.items()}
                if isinstance(value, list):
                    return [clean_paths(item) for item in value]
                if isinstance(value, str) and Path(value).is_absolute():
                    return path_label(value, repository)
                return value

            path.write_text(json.dumps(clean_paths(document), indent=2) + "\n", encoding="utf-8")
        elif path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames:
                    continue
                rows = list(reader)
            for row in rows:
                for key, value in row.items():
                    if key == "platform":
                        row[key] = platform_label()
                    elif value and Path(value).is_absolute():
                        row[key] = path_label(value, repository)
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=reader.fieldnames, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        elif path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
            text = re.sub(r"\b(?:macOS|Darwin)-[\w.-]+", platform_label(), text)
            path.write_text(text, encoding="utf-8")

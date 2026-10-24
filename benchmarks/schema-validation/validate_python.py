"""Run one Python API validation operation for the command-line benchmark."""

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("participant", choices=("jsonschema",))
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path, action="append")
    args = parser.parse_args()

    from jsonschema import Draft202012Validator

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validity = [validator.is_valid(json.loads(path.read_text(encoding="utf-8")))
                for path in args.data]
    print(f"validated {len(validity)} documents")
    return 0 if all(validity) else 1


if __name__ == "__main__":
    sys.exit(main())

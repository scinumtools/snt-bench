"""Run one Python API validation operation for the command-line benchmark."""

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("participant", choices=("jsonschema",))
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()

    from jsonschema import Draft202012Validator

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    data = json.loads(args.data.read_text(encoding="utf-8"))
    valid = Draft202012Validator(schema).is_valid(data)

    print("valid" if valid else "invalid")
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())

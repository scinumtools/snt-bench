#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
benchmark="pyunits"
args=("$@")
for ((index=0; index<${#args[@]}; index++)); do
  case "${args[index]}" in
    -b|--benchmark)
      if ((index + 1 >= ${#args[@]})); then
        echo "Missing value after ${args[index]}" >&2
        exit 2
      fi
      benchmark="${args[index+1]}"
      ((index+=1))
      ;;
    --benchmark=*) benchmark="${args[index]#*=}" ;;
  esac
done

case "$benchmark" in
  pyunits|pyunits-basic)
    if ((${#args[@]})); then
      exec "${PYTHON_LAUNCHER:-python3}" "$repo_dir/benchmarks/pyunits/run.py" "${args[@]}"
    fi
    exec "${PYTHON_LAUNCHER:-python3}" "$repo_dir/benchmarks/pyunits/run.py"
    ;;
  pyserial)
    serial_args=()
    for ((index=0; index<${#args[@]}; index++)); do
      case "${args[index]}" in
        -b|--benchmark) ((index+=1)) ;;
        --benchmark=*) ;;
        *) serial_args+=("${args[index]}") ;;
      esac
    done
    if ((${#serial_args[@]})); then
      exec "${PYTHON_LAUNCHER:-python3}" "$repo_dir/benchmarks/pyserial/run.py" "${serial_args[@]}"
    fi
    exec "${PYTHON_LAUNCHER:-python3}" "$repo_dir/benchmarks/pyserial/run.py"
    ;;
  *)
    echo "Unknown benchmark: $benchmark" >&2
    exit 2
    ;;
esac

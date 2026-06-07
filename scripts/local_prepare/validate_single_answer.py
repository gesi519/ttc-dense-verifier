#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_single_answer.py <answer.jsonl>", file=sys.stderr)
        return 2
    validator = Path(__file__).with_name("validate_answer_file.py")
    return subprocess.call([sys.executable, str(validator), sys.argv[1], "1"])


if __name__ == "__main__":
    raise SystemExit(main())

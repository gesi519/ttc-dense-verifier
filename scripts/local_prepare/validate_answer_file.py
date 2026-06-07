#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _wrong_memmove_direction(text: str) -> list[str]:
    failures: list[str] = []
    sentence_parts = re.split(r"(?<=[.!?。])\s+|\n+", text)
    dest_lt = re.compile(
        r"(?:backward|from the end)\s*\(\s*when\s+dest\s*<\s*src\s*\)|"
        r"dest\s*<\s*src[^.\n]{0,80}(?:requires|needs|uses|chooses|must use)"
        r"[^.\n]{0,80}(?:backward|from the end)|"
        r"(?:backward|from the end)[^.\n]{0,80}(?:is safe|is needed|preserves|protects)"
        r"[^.\n]{0,80}dest\s*<\s*src",
        re.I,
    )
    dest_gt = re.compile(
        r"forward\s*\(\s*when\s+dest\s*>\s*src\s*\)|"
        r"dest\s*>\s*src[^.\n]{0,80}(?:requires|needs|uses|chooses|must use)"
        r"[^.\n]{0,80}forward|"
        r"forward[^.\n]{0,80}(?:is safe|is needed|preserves|protects)"
        r"[^.\n]{0,80}dest\s*>\s*src",
        re.I,
    )
    for sentence in sentence_parts:
        if "memcpy" in sentence and "memmove" not in sentence:
            continue
        if dest_lt.search(sentence):
            failures.append("answer says memmove copies backward when dest < src")
        if dest_gt.search(sentence):
            failures.append("answer says memmove copies forward when dest > src")
    return failures


def _gives_memcpy_temporary_guarantee(text: str) -> bool:
    sentence_parts = re.split(r"(?<=[.!?。])\s+|\n+", text)
    current_subject = ""
    for sentence in sentence_parts:
        lower_sentence = sentence.lower()
        has_memcpy = "memcpy" in lower_sentence
        has_memmove = "memmove" in lower_sentence
        if has_memmove and not has_memcpy:
            current_subject = "memmove"
        elif has_memcpy and not has_memmove:
            current_subject = "memcpy"
        elif has_memcpy and has_memmove:
            current_subject = ""
        if "memcpy" not in lower_sentence:
            if current_subject != "memcpy":
                continue
        elif "memmove" in lower_sentence:
            continue
        if "temporary" in lower_sentence and ("as if" in lower_sentence or "temporary array" in lower_sentence):
            return True
    return False


def _validate_row(row: dict[str, object], row_number: int) -> tuple[list[str], list[str]]:
    text = str(row.get("text", ""))
    lower_text = text.lower()
    failures: list[str] = []
    warnings: list[str] = []

    if row.get("kind") != "chosen":
        failures.append(f"row {row_number}: kind should be chosen, got {row.get('kind')!r}")
    if row.get("model") != "deepseek-v4-pro":
        failures.append(f"row {row_number}: model should be deepseek-v4-pro, got {row.get('model')!r}")
    if len(text.strip()) < 1200:
        failures.append(f"row {row_number}: answer is too short")
    if "memcpy" not in text or "memmove" not in text:
        failures.append(f"row {row_number}: answer is missing memcpy or memmove")
    if text.count("```") % 2 != 0:
        failures.append(f"row {row_number}: Markdown code fences are not balanced")
    if not text.rstrip().endswith((".", "。", "!", "?", ")", "]", "`", '"', "'", "”", "’")):
        failures.append(f"row {row_number}: answer appears to end mid-sentence or mid-structure")
    if re.search(r"char\s+\w+\[\]\s*=\s*\"[^\"]+\";\s*.*memcpy\s*\([^;]*\+\s*\d+", text, re.S):
        failures.append(f"row {row_number}: snippet appears to write beyond a string-literal-sized char array")
    if re.search(r"memcpy\s*\([^;]*\+\s*6\s*,\s*[^;]*,\s*3\s*\)", text):
        failures.append(f"row {row_number}: snippet resembles out-of-bounds memcpy(buf + 6, ..., 3)")
    if "ill-formed" in lower_text:
        failures.append(f"row {row_number}: answer calls runtime undefined behavior ill-formed")
    if _gives_memcpy_temporary_guarantee(text):
        failures.append(f"row {row_number}: answer gives memcpy the temporary-buffer guarantee that belongs to memmove")
    if "memmove(buf + 2, buf + 1, 3)" in text and "abbcde" in text:
        failures.append(f"row {row_number}: memmove(buf + 2, buf + 1, 3) output is inconsistent")
    if (
        "memmove(buf + 1, buf, 3)" in text
        and 'printf("%s' in text
        and '"aabc"' in text
        and "aabcef" not in text
    ):
        failures.append(f"row {row_number}: partial-shift string drops unchanged suffix")
    if (
        "memmove(buf + 3, buf + 5, 5)" in text
        and ("copies backward" in lower_text or "copying backward" in lower_text)
    ):
        failures.append(f"row {row_number}: copy direction is wrong for dest < src")
    for direction_failure in _wrong_memmove_direction(text):
        failures.append(f"row {row_number}: {direction_failure}")
    if not ("undefined behavior" in lower_text or "behavior is undefined" in lower_text):
        warnings.append(f"row {row_number}: answer does not explicitly mention undefined behavior")
    if "assumption" not in lower_text and "precondition" not in lower_text:
        warnings.append(f"row {row_number}: answer may not state assumptions/preconditions clearly")
    if "limitation" not in lower_text:
        failures.append(f"row {row_number}: answer does not explicitly explain snippet limitations")

    return failures, warnings


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("Usage: validate_answer_file.py <answers.jsonl> [expected_count]", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    expected_count = int(sys.argv[2]) if len(sys.argv) == 3 else None

    rows: list[dict[str, object]] = []
    failures: list[str] = []
    warnings: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            failures.append(f"line {line_number}: {exc}")

    if expected_count is not None and len(rows) != expected_count:
        failures.append(f"expected {expected_count} rows, got {len(rows)}")

    prompt_ids = [str(row.get("prompt_id", "")) for row in rows]
    if len(prompt_ids) != len(set(prompt_ids)):
        failures.append("prompt_id values are not unique")

    for index, row in enumerate(rows, start=1):
        row_failures, row_warnings = _validate_row(row, index)
        failures.extend(row_failures)
        warnings.extend(row_warnings)

    print(f"[validation] file={path}")
    print(f"[validation] rows={len(rows)}")
    if rows:
        lengths = [len(str(row.get("text", ""))) for row in rows]
        print(f"[validation] characters min/avg/max={min(lengths)}/{sum(lengths)//len(lengths)}/{max(lengths)}")
    if warnings:
        print("[validation] warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if failures:
        print("[validation] FAIL:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

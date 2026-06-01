from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_training_inputs(
    *,
    rm_config: str | Path,
    sft_config: str | Path,
    rm_dataset_dir: str | Path,
    sft_dataset_dir: str | Path,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rm_report = _validate_rm_inputs(Path(rm_config), Path(rm_dataset_dir), errors, warnings)
    sft_report = _validate_sft_inputs(Path(sft_config), Path(sft_dataset_dir), errors, warnings)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "rm": rm_report,
        "sft": sft_report,
    }


def _validate_rm_inputs(
    config_path: Path,
    dataset_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    config = _read_yaml_scalars(config_path, errors)
    required = {
        "model_name_or_path",
        "stage",
        "do_train",
        "finetuning_type",
        "dataset",
        "eval_dataset",
        "dataset_dir",
        "template",
        "cutoff_len",
        "output_dir",
    }
    _require_keys(config, required, f"RM config {config_path}", errors)
    if config.get("stage") != "rm":
        errors.append(f"RM config stage must be rm, got {config.get('stage')}")
    _validate_bool(config, "do_train", True, f"RM config {config_path}", errors)
    _validate_checkpoint_overwrite_risk(config, f"RM config {config_path}", warnings)

    dataset_info = _read_dataset_info(dataset_dir, errors)
    train_name = str(config.get("dataset", ""))
    val_name = str(config.get("eval_dataset", ""))
    train_entry = _require_dataset_entry(dataset_info, train_name, "RM train", errors)
    val_entry = _require_dataset_entry(dataset_info, val_name, "RM eval", errors)
    _require_columns_mapping(
        train_entry,
        {
            "prompt": "instruction",
            "query": "input",
            "chosen": "chosen",
            "rejected": "rejected",
        },
        f"RM train dataset {train_name!r}",
        errors,
    )
    _require_columns_mapping(
        val_entry,
        {
            "prompt": "instruction",
            "query": "input",
            "chosen": "chosen",
            "rejected": "rejected",
        },
        f"RM eval dataset {val_name!r}",
        errors,
    )
    train_file = dataset_dir / str(train_entry.get("file_name", ""))
    val_file = dataset_dir / str(val_entry.get("file_name", ""))
    train_rows = _validate_jsonl_columns(train_file, ["instruction", "input", "chosen", "rejected"], errors)
    val_rows = _validate_jsonl_columns(val_file, ["instruction", "input", "chosen", "rejected"], errors)
    if train_entry and not train_entry.get("ranking", False):
        errors.append(f"RM dataset {train_name} must set ranking=true")
    if val_entry and not val_entry.get("ranking", False):
        errors.append(f"RM dataset {val_name} must set ranking=true")

    return {
        "config_path": str(config_path),
        "dataset_dir": str(dataset_dir),
        "dataset": train_name,
        "eval_dataset": val_name,
        "config_dataset_dir": str(config.get("dataset_dir", "")),
        "output_dir": str(config.get("output_dir", "")),
        "overwrite_output_dir": str(config.get("overwrite_output_dir", "")),
        "train_file": str(train_file),
        "val_file": str(val_file),
        "train_rows_checked": train_rows,
        "val_rows_checked": val_rows,
    }


def _validate_sft_inputs(
    config_path: Path,
    dataset_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    config = _read_yaml_scalars(config_path, errors)
    required = {
        "model_name_or_path",
        "stage",
        "do_train",
        "finetuning_type",
        "dataset",
        "dataset_dir",
        "template",
        "cutoff_len",
        "output_dir",
    }
    _require_keys(config, required, f"SFT config {config_path}", errors)
    if config.get("stage") != "sft":
        errors.append(f"SFT config stage must be sft, got {config.get('stage')}")
    _validate_bool(config, "do_train", True, f"SFT config {config_path}", errors)
    _validate_checkpoint_overwrite_risk(config, f"SFT config {config_path}", warnings)

    dataset_info = _read_dataset_info(dataset_dir, errors)
    dataset_name = str(config.get("dataset", ""))
    dataset_entry = _require_dataset_entry(dataset_info, dataset_name, "SFT train", errors)
    _require_columns_mapping(
        dataset_entry,
        {
            "prompt": "instruction",
            "query": "input",
            "response": "output",
        },
        f"SFT train dataset {dataset_name!r}",
        errors,
    )
    train_file = dataset_dir / str(dataset_entry.get("file_name", ""))
    train_rows = _validate_jsonl_columns(train_file, ["instruction", "input", "output"], errors)
    return {
        "config_path": str(config_path),
        "dataset_dir": str(dataset_dir),
        "dataset": dataset_name,
        "config_dataset_dir": str(config.get("dataset_dir", "")),
        "output_dir": str(config.get("output_dir", "")),
        "overwrite_output_dir": str(config.get("overwrite_output_dir", "")),
        "train_file": str(train_file),
        "train_rows_checked": train_rows,
    }


def _read_yaml_scalars(path: Path, errors: list[str]) -> dict[str, str]:
    if not path.exists():
        errors.append(f"Missing config file: {path}")
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _read_dataset_info(dataset_dir: Path, errors: list[str]) -> dict[str, Any]:
    path = dataset_dir / "dataset_info.json"
    if not path.exists():
        errors.append(f"Missing dataset_info.json: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid dataset_info.json at {path}: {exc}")
        return {}


def _require_dataset_entry(
    dataset_info: dict[str, Any],
    name: str,
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    entry = dataset_info.get(name)
    if not isinstance(entry, dict):
        errors.append(f"{label} dataset {name!r} is missing from dataset_info.json")
        return {}
    if not entry.get("file_name"):
        errors.append(f"{label} dataset {name!r} is missing file_name")
    columns = entry.get("columns")
    if not isinstance(columns, dict):
        errors.append(f"{label} dataset {name!r} is missing columns mapping")
    return entry


def _require_columns_mapping(
    entry: dict[str, Any],
    expected: dict[str, str],
    label: str,
    errors: list[str],
) -> None:
    if not entry:
        return
    columns = entry.get("columns")
    if not isinstance(columns, dict):
        return
    for key, value in expected.items():
        if columns.get(key) != value:
            errors.append(
                f"{label} columns.{key} must map to {value!r}, got {columns.get(key)!r}"
            )


def _validate_jsonl_columns(path: Path, required_columns: list[str], errors: list[str]) -> int:
    if not path.exists():
        errors.append(f"Missing JSONL dataset file: {path}")
        return 0
    if not path.is_file():
        errors.append(f"JSONL dataset path is not a file: {path}")
        return 0
    checked = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            checked += 1
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSONL at {path}:{line_number}: {exc}")
                continue
            missing = [column for column in required_columns if column not in row]
            if missing:
                errors.append(f"{path}:{line_number} missing columns: {', '.join(missing)}")
            if checked >= 5:
                break
    if checked == 0:
        errors.append(f"JSONL dataset file has no rows: {path}")
    return checked


def _require_keys(values: dict[str, str], required: set[str], label: str, errors: list[str]) -> None:
    for key in sorted(required - set(values)):
        errors.append(f"{label} missing required key: {key}")


def _validate_bool(
    values: dict[str, str],
    key: str,
    expected: bool,
    label: str,
    errors: list[str],
) -> None:
    if key not in values:
        return
    expected_value = "true" if expected else "false"
    if values[key].lower() != expected_value:
        errors.append(f"{label} {key} must be {expected_value}, got {values[key]}")


def _validate_checkpoint_overwrite_risk(
    values: dict[str, str],
    label: str,
    warnings: list[str],
) -> None:
    output_dir_value = values.get("output_dir", "")
    overwrite_value = values.get("overwrite_output_dir", "").lower()
    if not output_dir_value or overwrite_value != "true":
        return
    output_dir = Path(output_dir_value)
    if output_dir.exists() and any(output_dir.iterdir()):
        warnings.append(
            f"{label} has overwrite_output_dir=true and non-empty output_dir: {output_dir}"
        )

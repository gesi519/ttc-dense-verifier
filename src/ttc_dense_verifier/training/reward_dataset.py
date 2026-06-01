from __future__ import annotations

from typing import Any


def to_reward_model_record(pair: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(pair.get("metadata", {}))
    metadata["prompt_id"] = pair["prompt_id"]
    return {
        "instruction": pair["prompt"],
        "input": "",
        "chosen": pair["chosen"],
        "rejected": pair["rejected"],
        "metadata": metadata,
    }


def build_dataset_info(dataset_name: str, train_file: str, val_file: str) -> dict[str, Any]:
    columns = {
        "prompt": "instruction",
        "query": "input",
        "chosen": "chosen",
        "rejected": "rejected",
    }
    return {
        dataset_name: {
            "file_name": train_file,
            "ranking": True,
            "columns": columns,
        },
        f"{dataset_name}_val": {
            "file_name": val_file,
            "ranking": True,
            "columns": columns,
        },
    }

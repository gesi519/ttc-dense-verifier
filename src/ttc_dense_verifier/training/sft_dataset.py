from __future__ import annotations

from typing import Any


def to_sft_record(pair: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(pair.get("metadata", {}))
    metadata["prompt_id"] = pair["prompt_id"]
    return {
        "instruction": pair["prompt"],
        "input": "",
        "output": pair["chosen"],
        "metadata": metadata,
    }


def build_dataset_info(dataset_name: str, train_file: str) -> dict[str, Any]:
    return {
        dataset_name: {
            "file_name": train_file,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
            },
        }
    }

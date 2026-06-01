# Data Contract

This document defines the local data formation contract for TTC Dense Verifier
experiments. The contract covers prompt records, generation requests, answer
records, preference pairs, and train/validation/test split rules.

The data pipeline is intentionally local-first. Building prompt files, rendering
generation requests, joining answers into preference pairs, and writing splits do
not require GPU access or remote endpoints. Remote model calls only consume the
generation request JSONL after this contract has been satisfied.

## Pipeline Stages

```text
PromptRecord JSONL
 -> generation request JSONL
 -> positive AnswerRecord JSONL + negative AnswerRecord JSONL
 -> PreferencePair records
 -> train_preference.jsonl + val_preference.jsonl + test_prompts.jsonl
```

The supported CLI path is:

```bash
python -m ttc_dense_verifier.cli build-questions \
  --output data/raw_questions/questions.jsonl \
  --limit 5000

python -m ttc_dense_verifier.cli build-generation-requests \
  --questions data/raw_questions/questions.jsonl \
  --mode positive \
  --model Qwen2.5-32B-Instruct \
  --output data/generated_positive/positive_generation_requests.jsonl

python -m ttc_dense_verifier.cli build-generation-requests \
  --questions data/raw_questions/questions.jsonl \
  --mode negative \
  --model Qwen2.5-32B-Instruct \
  --output data/generated_negative/negative_generation_requests.jsonl

python -m ttc_dense_verifier.cli prepare-preferences \
  --questions data/raw_questions/questions.jsonl \
  --positive data/generated_positive/positive_answers.jsonl \
  --negative data/generated_negative/negative_answers.jsonl \
  --output-dir data/preference \
  --seed 13
```

## Prompt Records

Prompt records are the source of truth for user-facing questions.

Schema:

```json
{
  "prompt_id": "taxonomy-000001",
  "prompt": "Explain memcpy versus memmove in C or systems programming...",
  "source": "c_system_taxonomy",
  "metadata": {
    "topic": "string.h",
    "concept": "memcpy versus memmove",
    "task_type": "explanation",
    "scenario": "for a junior systems-programming student",
    "output_requirement": "Use Markdown headings and avoid unsupported claims."
  }
}
```

Required fields:

- `prompt_id`: stable string key used for joins and split assignment.
- `prompt`: non-empty user question text.
- `source`: prompt source name. Missing values are normalized to `unknown`.
- `metadata`: JSON object for non-semantic bookkeeping.

Prompt IDs must be stable across reruns for the same prompt corpus. Downstream
splits are assigned by `prompt_id`, so changing IDs changes experiment splits.

## Generation Requests

Generation requests are rendered instructions for producing answer records. They
are not answers and must not be used directly for verifier training.

Schema:

```json
{
  "prompt_id": "taxonomy-000001",
  "source_prompt": "Explain memcpy versus memmove in C or systems programming...",
  "generation_prompt": "You are generating training data for a verifier...\n\nUser question:\n...",
  "model": "Qwen2.5-32B-Instruct",
  "metadata": {
    "topic": "string.h",
    "concept": "memcpy versus memmove",
    "task_type": "explanation",
    "scenario": "for a junior systems-programming student",
    "output_requirement": "Use Markdown headings and avoid unsupported claims.",
    "source": "c_system_taxonomy",
    "generation_mode": "positive"
  }
}
```

Required fields:

- `prompt_id`: copied from the prompt record.
- `source_prompt`: original prompt text, copied without modification.
- `generation_prompt`: rendered instruction plus the user question.
- `model`: intended generator model label.
- `metadata.generation_mode`: either `positive` or `negative`.
- `metadata.source`: copied from the prompt record source.

Positive requests ask for rigorous technical answers. For code-related prompts,
they require professional code explanations, early introduction of relevant
functions, APIs, flags, and parameters, explicit parameter roles, return values,
side effects, ownership or lifetime constraints, error behavior, mechanism-level
causal reasoning, and a clear distinction between language or library guarantees
and implementation details. Negative requests ask for
controlled low-quality answers that stay on topic while introducing defects such
as UNIX-style status markers or emoji-like symbols (`❌`, `✅`, `⚠️`),
non-standard symbol noise (`>>>`, `==>`, repeated arrows), hollow slogans,
unsupported assertions, unexplained jargon stacking, broken heading or numbering
structure, missing causal chains, conclusion-first reasoning, and code-specific
explanation failures. Code-specific defects include unprofessional explanatory
style as a secondary signal, warnings or references to a function before its
parameters, return value, side effects, and argument roles are explained, and
thin mentions of functions, APIs, flags, or parameters without describing their
role in the code path or behavior change. The request must not ask the model to
reveal that the answer is intentionally bad.

## Answer Records

Answer records are aligned model outputs for one prompt.

Schema:

```json
{
  "prompt_id": "taxonomy-000001",
  "kind": "chosen",
  "text": "Use memmove when ranges may overlap because...",
  "model": "Qwen2.5-32B-Instruct",
  "metadata": {
    "generation_mode": "positive"
  }
}
```

Required fields:

- `prompt_id`: prompt key used for alignment.
- `kind`: semantic answer role. Expected values are `chosen` for positive
  answers and `rejected` for negative answers.
- `text`: generated answer text.
- `model`: generator model label.
- `metadata`: JSON object for generation details, defect tags, decoding
  parameters, or audit information.

During preference construction, records with missing aligned answers, empty
prompts, empty answer text, or near-duplicate chosen/rejected text are dropped
and counted in the data report.

## Preference Pairs

Preference pairs are the direct verifier-training contract.

Schema:

```json
{
  "prompt_id": "taxonomy-000001",
  "prompt": "Explain memcpy versus memmove in C or systems programming...",
  "chosen": "Use memmove when ranges may overlap because...",
  "rejected": ">>> memcpy is always fine!!!",
  "metadata": {
    "topic": "string.h",
    "concept": "memcpy versus memmove",
    "source": "c_system_taxonomy",
    "chosen_model": "Qwen2.5-32B-Instruct",
    "rejected_model": "Qwen2.5-32B-Instruct",
    "generation_mode": "negative"
  }
}
```

Required fields:

- `prompt_id`: copied from the prompt record.
- `prompt`: original user question text.
- `chosen`: preferred answer text.
- `rejected`: lower-quality answer text.
- `metadata`: merged prompt metadata plus model provenance.

The pair builder adds:

- `metadata.source` from the prompt record.
- `metadata.chosen_model` from the chosen answer record.
- `metadata.rejected_model` from the rejected answer record.

Rejected answer metadata is merged into pair metadata after prompt/model
metadata. This lets defect annotations from the negative generation path remain
available to evaluation and reporting.

## Split Rules

Splits are generated by `split_by_prompt_id`.

Rules:

- Split assignment is deterministic for a fixed input set, ratio tuple, and
  seed.
- Assignment is by unique `prompt_id`, not by row index.
- All rows with the same `prompt_id` must stay in the same split.
- Train, validation, and test prompt ID sets must be disjoint.
- Default ratios are `train_ratio=0.8`, `val_ratio=0.1`, and the remaining
  prompts go to test.
- For at least three unique prompt IDs, each split receives at least one prompt
  ID when ratios allow it.
- Empty input returns empty `train`, `val`, and `test` lists.

The CLI writes:

```text
data/preference/train_preference.jsonl
data/preference/val_preference.jsonl
data/preference/test_prompts.jsonl
data/preference/data_report.md
```

`test_prompts.jsonl` intentionally contains only:

```json
{
  "prompt_id": "taxonomy-000001",
  "prompt": "Explain memcpy versus memmove in C or systems programming...",
  "metadata": {}
}
```

It excludes `chosen` and `rejected` answers so TTC inference and final
evaluation do not consume training targets as prompts.

## Local Validation Expectations

For this contract, local validation means:

- JSONL rows are parseable JSON objects.
- Prompt, request, answer, and pair rows contain the schema fields above.
- Preference construction drops invalid or unusable pairs and reports counts.
- Split prompt IDs are disjoint across train, validation, and test.
- No model endpoint, GPU job, checkpoint load, or remote service is needed.

Required local checks:

```bash
PYTHONPATH=src python3 -m unittest tests.test_data_pipeline tests.test_generation_requests -v
PYTHONPATH=src python3 -m compileall -q src tests
```

# TTC Dense Verifier Evaluation

- run_id: `P20SUMMARY_EVAL_P19_20260606_135000`
- created_at: `2026-06-06T14:33:28.502410+00:00`
- git_commit: `not-a-git-checkout`
- merged_rows: `2000`
- merge_ok: `True`

## Main Metrics

| method | count | abnormal_symbol_count_mean | code_fence_mismatch_mean | slogan_phrase_count_mean | word_count_mean | abnormal_symbol_count_total | code_fence_mismatch_total | slogan_phrase_count_total | repeated_line_count_total | latency_ms_mean | verifier_call_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw_32b | 500 | 0 | 0 | 0 | 427.1220 | 0 | 0 | 0 | 1626 | 0 | 0 |
| sft_32b | 500 | 0 | 0 | 0 | 429.3240 | 0 | 0 | 0 | 1738 | 0 | 0 |
| ttc_beam | 500 | 0 | 0 | 0 | 457.7780 | 0 | 0 | 0 | 2156 | 27821.9010 | 4 |
| ttc_penalty | 500 | 0 | 0 | 0 | 446.9700 | 0 | 0 | 0 | 954 | 28575.7552 | 4 |

## Static Metric Summary

```json
{
  "raw_32b": {
    "abnormal_symbol_count_mean": 0.0,
    "character_count_mean": 2946.426,
    "code_fence_mismatch_mean": 0.0,
    "count": 500,
    "heading_count_mean": 5.8,
    "list_item_count_mean": 9.194,
    "repeated_line_count_mean": 3.252,
    "slogan_phrase_count_mean": 0.0,
    "word_count_mean": 427.122
  },
  "sft_32b": {
    "abnormal_symbol_count_mean": 0.0,
    "character_count_mean": 2958.268,
    "code_fence_mismatch_mean": 0.0,
    "count": 500,
    "heading_count_mean": 5.812,
    "list_item_count_mean": 9.134,
    "repeated_line_count_mean": 3.476,
    "slogan_phrase_count_mean": 0.0,
    "word_count_mean": 429.324
  },
  "ttc_beam": {
    "abnormal_symbol_count_mean": 0.0,
    "character_count_mean": 3177.856,
    "code_fence_mismatch_mean": 0.0,
    "count": 500,
    "heading_count_mean": 5.626,
    "list_item_count_mean": 10.186,
    "repeated_line_count_mean": 4.312,
    "slogan_phrase_count_mean": 0.0,
    "word_count_mean": 457.778
  },
  "ttc_penalty": {
    "abnormal_symbol_count_mean": 0.0,
    "character_count_mean": 3080.562,
    "code_fence_mismatch_mean": 0.0,
    "count": 500,
    "heading_count_mean": 5.432,
    "list_item_count_mean": 10.212,
    "repeated_line_count_mean": 1.908,
    "slogan_phrase_count_mean": 0.0,
    "word_count_mean": 446.97
  }
}
```

## Artifacts

- merged_output: `reports/eval/merged_raw_sft_ttc_p19.jsonl`
- metrics_csv: `reports/eval/metrics_p19.csv`
- human_review_csv: `reports/eval/assets_raw_sft_ttc_p19/human_review.csv`
- judge_requests: `reports/eval/assets_raw_sft_ttc_p19/judge_requests.jsonl`
- figures_dir: `reports/figures/raw_sft_ttc_p19`

## Notes

Static metrics are automatic checks for visible formatting and writing defects. They do not replace human or model-judge evaluation of technical correctness.
All three methods use the same 500 test prompts.

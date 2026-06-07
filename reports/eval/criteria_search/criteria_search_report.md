# P21 TTC 判断标准搜索报告

- created_at: `2026-06-07T05:35:31.997763+00:00`
- val_rm: `data/training/rm/val_rm.jsonl`
- validation_pairs: `500`
- merged_output: `reports/eval/merged_raw_sft_ttc_p19.jsonl`
- output_scores: `reports/eval/verifier_score_raw_sft_ttc_p19.jsonl`
- criteria_grid: `reports/eval/criteria_search/criteria_grid.csv`
- method_scores: `reports/eval/criteria_search/method_scores.csv`

## 测试方式与合理性

本测试先在 RM 验证集上搜索评价标准。每个标准都必须把人工构造的 chosen 答案排在 rejected 答案前面，之后才用于比较 raw、SFT、P15 TTC 和 P19 TTC。这样做的目的，是避免事后选择只对 TTC 有利、但不能识别真实坏答案的指标。

候选标准以 verifier reward 为主项，并加入可解释的缺陷惩罚：重复行、答案长度、异常符号/代码块不匹配/空洞短语。搜索不会重新生成答案，不修改模型权重，也不改测试集。

## 选定标准

```json
{
  "abnormal_penalty": 2.0,
  "length_penalty_per_100_words": 0.0,
  "mean_margin": 33.298494912564756,
  "median_margin": 32.42417812347412,
  "min_margin": 8.179616034030914,
  "pairwise_accuracy": 1.0,
  "repeated_penalty": 0.0
}
```

选定逻辑：先保留验证集 pairwise accuracy 接近最优的标准，再选择 mean_margin 最大的一个；若 mean_margin 接近，再选择惩罚更轻的标准。这样可以避免选择虽然准确但区分度较弱的标准。

## 验证集前 10 个标准

| repeated_penalty | length_penalty_per_100_words | abnormal_penalty | pairwise_accuracy | mean_margin | median_margin | min_margin |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0000 | 0.0000 | 2.0000 | 1.0000 | 33.2985 | 32.4242 | 8.1796 |
| 0.0000 | 0.0200 | 2.0000 | 1.0000 | 33.1806 | 32.2903 | 8.0286 |
| 0.0000 | 0.0500 | 2.0000 | 1.0000 | 33.0037 | 32.1335 | 7.8021 |
| 0.0000 | 0.1000 | 2.0000 | 1.0000 | 32.7088 | 31.9431 | 7.4246 |
| 0.1000 | 0.0000 | 2.0000 | 1.0000 | 32.6431 | 31.9372 | 6.7796 |
| 0.1000 | 0.0200 | 2.0000 | 1.0000 | 32.5252 | 31.8023 | 6.6286 |
| 0.0000 | 0.1500 | 2.0000 | 1.0000 | 32.4140 | 31.6522 | 7.0471 |
| 0.1000 | 0.0500 | 2.0000 | 1.0000 | 32.3483 | 31.5693 | 6.4021 |
| 0.1000 | 0.1000 | 2.0000 | 1.0000 | 32.0534 | 31.2328 | 6.0246 |
| 0.1000 | 0.1500 | 2.0000 | 1.0000 | 31.7586 | 30.9227 | 5.6471 |

## 四组输出排序

| method | count | criterion_score_mean | criterion_score_median | verifier_score_mean | repeated_line_total | word_count_mean | abnormal_symbol_total | code_fence_mismatch_total | slogan_phrase_total | latency_ms_mean | verifier_call_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ttc_beam | 500 | 1.6916 | 2.0190 | 1.6916 | 2156 | 457.7780 | 0 | 0 | 0 | 27821.9010 | 4.0000 |
| ttc_penalty | 500 | 1.2310 | 1.4010 | 1.2310 | 954 | 446.9700 | 0 | 0 | 0 | 28575.7552 | 4.0000 |
| raw_32b | 500 | -0.2235 | 0.1126 | -0.2235 | 1626 | 427.1220 | 0 | 0 | 0 | 0.0000 | 0.0000 |
| sft_32b | 500 | -0.2293 | -0.0221 | -0.2293 | 1738 | 429.3240 | 0 | 0 | 0 | 0.0000 | 0.0000 |

## 结论

合适的判断标准不应是单一静态格式分，也不应只看未校准的 verifier reward。当前更合理的主质量标准是“标签校准后的 verifier reward 加异常符号/格式噪声惩罚”。重复行和长度不应直接并入主质量分，因为验证集标签没有显示它们能稳定区分 chosen/rejected；它们更适合作为解码副作用 guardrail 单独报告。

# P20 四组统一评测决策报告

- created_at: `2026-06-06T14:39:28.918430+00:00`
- metrics_csv: `reports/eval/metrics_p19.csv`
- score_summary: `reports/eval/verifier_score_raw_sft_ttc_p19_summary.json`
- failure_samples: `reports/eval/p20_ttc_penalty_regression_samples.md`

## 测试方式与合理性

本报告读取 P20 四组统一评测的脚本产物，不重新生成答案，也不修改任何模型权重。四组输出来自同一 500 条测试提示，合并脚本已确认每组 500 条、无缺失、无重复、无空答案。静态指标用于检查 P15 暴露的重复和冗长问题，verifier 全量评分用于检查 P19 惩罚项是否破坏原有 verifier 偏好收益。

这种测试合理，因为 P19 的实验变量只在解码期 rerank score 中加入长度和重复行惩罚。若重复降低但 verifier 分数明显下降，说明惩罚过强或目标函数需要调参，而不能直接宣称 P19 优于 P15。

## 主要指标

| method | verifier_mean | verifier_median | repeated_line_total | word_count_mean | latency_ms_mean | verifier_call_count_mean |
|---|---:|---:|---:|---:|---:|---:|
| raw_32b | -0.2235 | 0.1126 | 1626 | 427.122 | 0 | 0 |
| sft_32b | -0.2293 | -0.0221 | 1738 | 429.324 | 0 | 0 |
| ttc_beam | 1.6916 | 2.0190 | 2156 | 457.778 | 27821.900957750157 | 4 |
| ttc_penalty | 1.2310 | 1.4010 | 954 | 446.97 | 28575.755227072164 | 4 |

## 结论

P19 相对 P15 将 repeated_line_total 从 2156 降到 954，下降约 55.8%；word_count_mean 从 457.778 降到 446.970。这说明长度和重复惩罚确实缓解了 P15 的可见重复问题。

代价是 verifier mean 从 1.6916 降到 1.2310，下降 0.4605。P19 相对 P15 只赢 198/500，输 302/500。因此 P19 不能作为最终优于 P15 的结论，只能作为证明“解码期正则化有效但当前惩罚过强”的诊断实验。

相对 raw/SFT，P19 仍分别赢 386/500 和 385/500，说明 TTC 主线并未失败；失败点在 P19 与 P15 之间的质量-简洁性权衡。

## 下一步建议

不建议直接清理并进入最终论文报告。下一轮应运行较轻惩罚的 P21：保留 repeated_line_penalty=0.5，将 length_penalty_per_100_words 从 0.15 降到 0.05，或同时增加一个只惩罚重复行、不惩罚长度的消融。预期影响是重新调用 32B generator 和 7B verifier，500 条约 4 小时，不改模型权重、不写 checkpoint，只新增 outputs/ttc、runs/ttc 和 reports/eval 下的本项目产物。

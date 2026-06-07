# TTC 实验测试报告

## 测试范围

本次测试覆盖 raw 32B、SFT 32B、TTC beam 三组输出。三组都使用同一份 `data/preference/test_prompts.jsonl`，每组 500 条。

## 完整性测试

- raw_32b: 500/500，无缺失、无重复、无空答案。
- sft_32b: 500/500，无缺失、无重复、无空答案。
- ttc_beam: 500/500，无缺失、无重复、无空答案。
- ttc trace: 500/500，每条 TTC 输出都有对应搜索轨迹。

## 静态指标测试

| method | abnormal_symbol_mean | code_fence_mismatch_mean | slogan_phrase_mean | word_count_mean | repeated_line_total | latency_ms_mean | verifier_calls_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| raw_32b | 0 | 0 | 0 | 427.122 | 1626 | 0 | 0 |
| sft_32b | 0 | 0 | 0 | 429.324 | 1738 | 0 | 0 |
| ttc_beam | 0 | 0 | 0 | 457.778 | 2156 | 27821.900957750157 | 4 |

静态指标结论：三组在符号噪声、代码块闭合、空洞口号方面都没有触发明显缺陷。TTC 的平均字数更高，重复行总数也更高，因此静态指标不能单独证明 TTC 更好。

## Verifier 全量评分测试

| method | mean | median | min | max |
| --- | ---: | ---: | ---: | ---: |
| raw_32b | -0.2235 | 0.1126 | -11.0914 | 6.4852 |
| sft_32b | -0.2293 | -0.0221 | -11.5009 | 6.1453 |
| ttc_beam | 1.6916 | 2.0190 | -9.1856 | 6.8909 |

- TTC 高于 raw: 432/500。
- TTC 高于 SFT: 434/500。
- TTC 不高于 raw: 68/500。
- TTC 不高于 SFT: 66/500。

Verifier 评分结论：TTC 在训练好的 verifier 目标上明显优于 raw 和 SFT，说明解码期重排确实在优化 verifier 偏好的答案。但这个指标和 TTC 选择器共享同一个 verifier，因此不能作为唯一论文结论。

## 失败样本

已导出 `reports/eval/ttc_failure_cases_sample.md`。这些样本用于检查 TTC 输分原因，包括 baseline 更贴合角色、TTC 更冗长、或者 verifier 对某些措辞偏好不稳定。

## 当前判断

当前结果是混合的：TTC 在 verifier 分数上显著更好，但在静态格式指标上没有优势，并且重复行更多、推理成本更高。下一步不应直接写最终正向结论，而应补充人工或 judge 评测，并尝试较低 beta 或更强长度惩罚的 TTC 配置。

## 建议下一轮测试

1. 固定同一 500 条测试集，运行 beta=0.3 或 beta=0.5 的 TTC。
2. 增加长度归一化或重复惩罚，避免 verifier 偏好长答案。
3. 对 `ttc_failure_cases_sample.md` 做人工标注，判断是 verifier 分数问题还是实际质量问题。
4. 用 judge requests 做外部评测，避免只依赖训练 verifier。

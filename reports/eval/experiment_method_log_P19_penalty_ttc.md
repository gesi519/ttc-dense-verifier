# P19 Penalty TTC 测试方法日志

## 背景

P15 TTC beam full 已完成 500 条。完整性、trace 和 verifier 全量评分均通过；TTC 在 verifier 分数上明显优于 raw/SFT，但静态指标显示 TTC 的重复行总数更高，平均答案更长，推理成本也更高。

## 关键诊断

对 P15 的前 100 条 branch score 检查发现，`generator_logprob` 全部为 0。这意味着当前总分：

```text
total_score = generator_logprob + beta * verifier_reward
```

实际退化为：

```text
total_score = beta * verifier_reward
```

当 `beta > 0` 时，仅修改 beta 不会改变候选排序，只会线性缩放分数。因此直接跑 beta=0.3 或 beta=0.5 不是有效消融，不能回答重复行增多的问题。

## 新测试方式

本轮测试改为带惩罚项的 TTC rerank：

```text
adjusted_score = verifier_reward
               - length_penalty_per_100_words * word_count / 100
               - repeated_line_penalty * repeated_line_count
```

固定条件：

- 测试集仍为 `data/preference/test_prompts.jsonl` 的同一 500 条。
- generator 仍为 frozen `Qwen2.5-32B-Instruct`。
- verifier 仍为 `Qwen2.5-7B-RM-P10MULTI_20260604_055439`。
- beam_width=4，expansions_per_step=4，max_steps=1，与 P15 保持一致。
- 只改变 rerank scoring，不改 generator 权重，不改 verifier 权重，不改数据集。

## 合理性

这个测试直接对应 P15 的失败现象：TTC 的 verifier 分数更高，但输出更长、重复行更多。惩罚项不会主动降低代码解释质量，而是约束 verifier 对冗长或重复候选的偏好。若 P19 保持 verifier 胜率，同时降低 repeated_line_total 和 word_count，则说明解码期目标需要加入正则化；若 P19 verifier 分数大幅下降或内容变差，则说明重复问题不能只靠轻量 rerank 惩罚解决，需要重新审查 verifier 训练数据或引入外部 judge。

## 通过标准

P19 不要求在所有指标上优于 P15，但至少应满足：

1. 完整性：500 条输出、500 条 trace，无缺失、无重复、无空答案。
2. 静态指标：repeated_line_total 低于 P15 的 2156。
3. verifier 评分：TTC penalty 的 mean 不应大幅低于 raw/SFT，且应记录相对 P15 的下降幅度。
4. 失败样本：输出 penalty 版本相对 P15 的劣化样本，供人工判断。

## Smoke 测试记录

启动方式：

```bash
PYTHONPATH=src python scripts/remote_infer/run_ttc_incremental.py \
  --config configs/infer/ttc_beam_raw32b_penalty_smoke.json
```

测试方式：

- 使用同一测试集 `data/preference/test_prompts.jsonl` 的前 5 条。
- 每条仍生成 4 个候选并调用 verifier 评分。
- 检查输出行数、trace 行数、prompt_id 去重、空答案、惩罚元数据字段。
- 与 P15 前 5 条比较 repeated_line_total 和 word_count_mean。

合理性：

smoke 测试不用于论文结论，只用于确认新 scoring 在真实 generator/verifier 链路中可运行，并快速观察惩罚项是否直接缓解 P15 暴露的重复和冗长问题。由于数据量只有 5 条，它只能作为启动 full run 的工程门槛，不能替代 500 条全量评测。

结果：

- P19 smoke 输出 5 条，trace 5 条。
- 无重复 prompt_id，无空答案。
- 惩罚元数据完整：`raw_verifier_reward`、`adjusted_score`、`word_count`、`repeated_line_count`、`length_penalty`、`repeated_line_penalty`、`total_penalty` 均存在。
- P15 前 5 条 repeated_line_total 为 16，word_count_mean 为 460.0。
- P19 smoke 前 5 条 repeated_line_total 为 5，word_count_mean 为 449.2。

决策：

smoke 通过，可以启动 P19 full 500 条。full run 的结论仍必须以后续完整性检查、静态指标、verifier 全量评分和失败样本审查为准。

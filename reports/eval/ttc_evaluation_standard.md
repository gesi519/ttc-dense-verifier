# TTC 提升判断标准

## 标准来源

本标准来自 P21 判断标准搜索：

- 验证数据：`data/training/rm/val_rm.jsonl`，500 对 chosen/rejected。
- 输出数据：`reports/eval/merged_raw_sft_ttc_p19.jsonl`，raw、SFT、P15 TTC、P19 TTC 各 500 条。
- verifier 分数：`reports/eval/verifier_score_raw_sft_ttc_p19.jsonl`。
- 搜索报告：`reports/eval/criteria_search/criteria_search_report.md`。

## 主质量标准

主质量分定义为：

```text
quality_score = verifier_reward - 2.0 * style_noise_count
```

其中：

```text
style_noise_count =
  abnormal_symbol_count
  + code_fence_mismatch
  + slogan_phrase_count
```

这个标准在 RM 验证集上的结果：

- pairwise_accuracy: 1.0
- mean_margin: 33.2985
- median_margin: 32.4242
- min_margin: 8.1796

合理性：

1. verifier_reward 捕捉技术解释质量、因果链、边界条件和代码讲解完整性。
2. style_noise_count 对应用户明确指出的负向问题：符号噪声、代码块错误、空洞表述。
3. 该标准先在 chosen/rejected 标签上通过验证，再用于比较 TTC 和 baseline，因此不是事后为 TTC 定制。

## 副作用 Guardrail

重复行和长度不进入主质量分，而作为副作用单独报告：

```text
repeated_line_total
word_count_mean
latency_ms_mean
verifier_call_count_mean
```

原因：

验证集搜索显示，长度惩罚和重复行惩罚不是区分 chosen/rejected 的必要主项；把它们直接并入主质量分会把“更详细的技术解释”误判为低质量。它们更适合用于判断 TTC 解码是否产生副作用。

## 可以声明 TTC 提升的条件

对一个 TTC run，可以声明“相对 baseline 有提升”，需要同时满足：

1. 完整性通过：输出 500 条，trace 500 条，无缺失、无重复、无空答案。
2. 主质量分均值高于 raw_32b 和 sft_32b。
3. 主质量分 pairwise win rate 相对 raw_32b 和 sft_32b 均超过 70%。
4. style_noise_count 总量不高于 raw_32b 和 sft_32b。
5. repeated_line_total、word_count_mean 和 latency_ms_mean 必须单独报告，不能隐藏。

对一个 TTC run，可以声明“更适合部署或论文主结果”，还需要：

1. repeated_line_total 不高于 raw_32b 和 sft_32b 的较高者。
2. word_count_mean 不明显高于 raw_32b 和 sft_32b 的较高者。
3. 若主质量分低于另一个 TTC 变体，必须说明这是质量和副作用之间的权衡，不能只报告有利指标。

## 当前结果解释

P15 `ttc_beam`：

- 主质量分均值：1.6916，高于 raw_32b 的 -0.2235 和 sft_32b 的 -0.2293。
- 相对 raw/SFT 的 verifier pairwise 胜率分别为 432/500 和 434/500。
- repeated_line_total 为 2156，高于 raw_32b 的 1626 和 sft_32b 的 1738。

解释：

P15 可以证明 TTC 主线提升了 verifier 认可的技术质量，但存在重复行副作用，不能单独作为最终部署标准。

P19 `ttc_penalty`：

- 主质量分均值：1.2310，高于 raw_32b 和 sft_32b。
- 相对 raw/SFT 的 pairwise 胜率分别为 386/500 和 385/500。
- repeated_line_total 为 954，低于 raw_32b、sft_32b 和 P15。
- 相对 P15 的主质量分下降，P19 只赢 P15 198/500。

解释：

P19 可以证明 TTC 在加入解码期副作用控制后，仍然相对 raw/SFT 保持主质量提升，同时显著降低重复行。它不证明 P19 优于 P15 的技术质量，而是证明 TTC 的质量和副作用可以通过解码目标进行权衡。

## 后续实验建议

下一轮 P21/P22 不应继续盲目寻找单一总分，而应固定上述标准：

1. 主质量分用于判断技术质量提升。
2. repeated_line_total 和 word_count_mean 用于判断副作用。
3. latency_ms_mean 和 verifier_call_count_mean 用于判断计算成本。

建议实验：

- P21-light-length：`length_penalty_per_100_words=0.05`，`repeated_line_penalty=0.5`。
- P22-repeat-only：`length_penalty_per_100_words=0.0`，`repeated_line_penalty=0.5`。

目标不是让所有指标同时最大，而是寻找 Pareto 前沿：主质量分显著高于 raw/SFT，同时重复行不超过 baseline。

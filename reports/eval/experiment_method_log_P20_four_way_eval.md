# P20 四组统一评测方法日志

## 测试方式

本轮评测比较四组输出：

- `raw_32b`：冻结 Qwen2.5-32B 原始 baseline。
- `sft_32b`：Qwen2.5-32B LoRA SFT baseline。
- `ttc_beam`：P15 原始 TTC beam rerank。
- `ttc_penalty`：P19 带长度和重复行惩罚的 TTC rerank。

固定条件：

- 四组都使用同一测试集 `data/preference/test_prompts.jsonl` 的 500 条。
- 不修改 generator 权重、verifier 权重、测试集或已有输出。
- 评测只读取已有 JSONL，并写入 `reports/eval/` 与 `reports/figures/`。
- 完整性检查要求每组 500 条，无缺失、无重复、无空答案。

评测内容：

1. 合并四组输出为 `reports/eval/merged_raw_sft_ttc_p19.jsonl`。
2. 运行静态指标，统计异常符号、代码块不匹配、空洞短语、重复行、长度。
3. 导出表格、human review CSV、judge request JSONL 和图像源文件。
4. 调用同一个 P10MULTI verifier 服务，对四组答案做全量 reward 评分。
5. 输出 P19 相对 raw、SFT、P15 的 pairwise win/loss。

## 合理性

P19 的目标不是重新证明 TTC 一定优于所有 baseline，而是验证一个具体诊断：P15 的 verifier 分数更高，但答案更长、重复行更多。静态指标能直接观察重复和冗长是否缓解；verifier 全量评分能检查惩罚项是否破坏原本的 verifier 偏好收益；pairwise win/loss 能避免只看均值掩盖样本级劣化。

这个评测不依赖人工挑样，不修改被评测输出，不把 P19 结果混入 P15 目录，因此能复现并保留失败样本。

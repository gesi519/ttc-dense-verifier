# Constraints Layer

## 1. 研究约束

- 核心贡献是 TTC Dense Verifier，不是单纯的 32B SFT。
- `raw_generator`、`sft_baseline` 和 `ttc_*` 必须使用同一测试集。
- SFT baseline 只作为传统方法对照，不应改变 TTC 方法的测试集或指标。
- LLM-as-a-Judge 不能作为唯一证据，必须同时报告静态指标和代码能力 guardrail。
- 结论必须能追溯到配置、输入、输出、日志和指标表。

## 2. 数据约束

偏好样本必须包含：

```json
{
  "prompt_id": "q_000001",
  "prompt": "解释 memcpy 和 memmove 的区别。",
  "chosen": "memcpy 要求源区间和目标区间不重叠...",
  "rejected": "memcpy 是内存复制的灵魂，速度飞快...",
  "split": "train"
}
```

必须遵守：

- `prompt_id` 必须稳定。
- `chosen` 和 `rejected` 不得相同。
- train/val/test 不得交叉。
- 测试集不得参与 verifier 训练或解码超参选择。
- 样本生成请求和样本回答都要保留。

## 3. 训练约束

必须记录：

- 基座模型名称。
- 数据路径与数据版本。
- 训练配置文件路径。
- LoRA rank、alpha、target。
- cutoff length、batch size、gradient accumulation。
- learning rate、epoch、seed。
- checkpoint 输出目录。

禁止：

- 覆盖已有 checkpoint。
- 未运行训练输入校验就启动训练。
- 把本地私有绝对路径写入配置。
- 把真实模型权重提交到 Git。

训练前置检查：

```bash
PYTHONPATH=src python -m ttc_dense_verifier.cli validate-training-inputs \
  --rm-config configs/training/verifier_rm_qwen7b.yaml \
  --sft-config configs/training/generator_sft_qwen32b_lora.yaml \
  --rm-dataset-dir data/training/rm \
  --sft-dataset-dir data/training/sft \
  --output outputs/logs/training_input_validation.json
```

## 4. 推理约束

每条推理输出必须记录：

- prompt id。
- method。
- final answer。
- decoding parameters。
- generator score 或 logprob。
- verifier score。
- branch scores 或 trace 摘要。
- latency 和 verifier call count，若可用。

禁止：

- 只保存最终回答。
- 在 baseline 与 TTC 之间使用不同 prompt 集。
- 在未记录 `beta`、beam width、temperature、top_p 时使用结果做论文表格。

## 5. 评测约束

必须至少包含：

- abnormal symbol count。
- code fence mismatch。
- slogan phrase count。
- answer length。
- code guardrail。
- judge request 或人工 review 表。
- error breakdown。

禁止：

- 改写模型输出后再评测。
- 只展示平均分，不展示错误案例。
- 只汇报 TTC 胜出的指标。

## 6. 远程约束

远程长任务前必须确认：

```bash
nvidia-smi
tmux -V
python -c "import torch; print(torch.cuda.is_available())"
llamafactory-cli --help
```

必须通过：

```bash
bash scripts/remote_deploy/generated/health_check.sh
```

禁止：

- 手动编辑 generated runbook 后不回写生成逻辑。
- 在 verifier checkpoint 切换后跳过服务探测。
- 在任务失败时继续执行后续阶段。

## 7. Git 约束

不得提交：

```text
真实 checkpoint
真实大规模数据
模型权重
长任务日志
API key
.env
```

允许提交：

```text
配置文件
小样例 JSONL
测试
文档
生成脚本
论文图表源文件
```

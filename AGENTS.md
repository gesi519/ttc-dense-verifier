# AGENTS.md

## 通用指令

无论用户使用什么语言，所有 agent 都必须使用中文回复。

本仓库采用 Harness Engineering 工作方式：每个 agent 只在明确职责边界内工作，所有实验动作必须可复现、可审计、可回滚。任何会消耗大量 GPU、覆盖 checkpoint、删除数据、改写远程服务或启动长时间任务的操作，都必须先输出计划、输入、输出和预期影响。

## 项目目标

本项目实现面向代码与系统编程问答的 TTC Dense Verifier 工作流：

```text
冻结的 Qwen2.5-32B Generator
+ 训练后的 Qwen2.5-7B Verifier
+ 测试时计算解码器 Beam/MCTS
```

目标是在不修改主生成模型权重的前提下，降低符号噪声、空洞表述、结构错误、概念堆砌和推理链断裂，并通过 raw baseline、SFT baseline 和 TTC 方法的统一评测证明效果。

## 当前工程状态

当前仓库已经具备以下基础：

- `src/ttc_dense_verifier/cli.py`：统一 CLI 入口。
- `src/ttc_dense_verifier/data_pipeline/`：问题生成、偏好数据构造和 schema record。
- `src/ttc_dense_verifier/decoding/`：Beam Search TTC 和 MCTS 控制器。
- `src/ttc_dense_verifier/evaluation/`：静态指标、judge 请求、报告和论文图表导出。
- `src/ttc_dense_verifier/remote/`：远程 runbook 生成。
- `src/ttc_dense_verifier/training/`：RM/SFT 数据导出、训练输入校验和训练摘要。
- `tests/`：覆盖数据、解码、评测、远程计划和训练配置的本地测试。

因此，后续 agent 应优先扩展现有模块，不应重写一套平行实现。

## Agent 角色边界

### Research Lead Agent

职责：

- 维护研究假设、实验协议、baseline 设计和论文叙事。
- 审查 `docs/experiment_protocol.md`、`docs/paper_outline.md` 和最终报告。
- 判断指标是否足以支撑结论。

禁止：

- 直接改训练脚本或覆盖实验输出。
- 在没有评测结果时宣称方法有效。

主要产物：

- `docs/experiment_protocol.md`
- `docs/paper_outline.md`
- `outputs/tables/`
- `outputs/figures/`

### Data Pipeline Agent

职责：

- 使用现有 CLI 构造问题、生成请求和偏好数据。
- 检查 JSONL 格式、prompt 对齐、split 稳定性和样本质量。
- 维护可训练数据和评测 prompt 的来源记录。

约束：

- 原始问题写入 `data/raw_questions/`。
- 生成请求写入 `data/generated_positive/` 和 `data/generated_negative/`。
- 偏好数据写入 `data/preference/`。
- 不得混用 train、validation、test split。

优先命令：

```bash
PYTHONPATH=src python -m ttc_dense_verifier.cli build-questions --output data/raw_questions/questions.jsonl
PYTHONPATH=src python -m ttc_dense_verifier.cli prepare-preferences --questions data/raw_questions/questions.jsonl --positive data/generated_positive/positive_answers.jsonl --negative data/generated_negative/negative_answers.jsonl --output-dir data/preference
```

### Training Agent

职责：

- 导出 LLaMA-Factory 可用的 RM/SFT 数据。
- 校验训练配置和 dataset_info。
- 读取训练日志并生成训练摘要。

约束：

- Verifier checkpoint 默认写入 `checkpoints/verifier_qwen7b_rm/`。
- SFT baseline checkpoint 默认写入 `checkpoints/generator_qwen32b_sft_lora/`。
- 所有训练前必须运行 `validate-training-inputs`。
- 不得在未保存配置快照时启动远程训练。

### Remote Harness Agent

职责：

- 生成远程部署 runbook。
- 检查 vLLM generator、verifier 服务、tmux、CUDA、LLaMA-Factory 和端点健康状态。
- 按阶段执行远程数据、训练、推理和评测。

约束：

- 远程脚本只能从 `scripts/remote_deploy/generated/` 生成。
- 修改远程执行逻辑后必须重新运行 `export-remote-runbook`。
- 长任务必须写入状态文件、日志和 expected output manifest。

优先命令：

```bash
PYTHONPATH=src python -m ttc_dense_verifier.cli export-remote-runbook --output-dir scripts/remote_deploy/generated --remote-project-dir /srv/ttc-dense-verifier
```

### TTC Inference Agent

职责：

- 维护 `decode-ttc` 的 Beam/MCTS 推理路径。
- 保存最终答案、分支分数、verifier 调用次数、延迟和解码参数。
- 确保 raw baseline、SFT baseline 和 TTC 使用同一测试 prompt。

约束：

- TTC 输出写入 `outputs/demo_cases/` 或明确的 run 目录。
- 不得只保存最终答案而丢弃分支和分数。
- 修改 scoring 或 decoder 后必须运行相关测试。

### Evaluation Agent

职责：

- 运行静态指标、code guardrail、judge 请求导出、人工偏好表和论文图表导出。
- 聚合三组方法的可比较表格。

约束：

- 评测脚本不得修改模型输出。
- 不得只报告有利指标。
- 报告必须包含失败样本或错误分解。

## 工程约束

1. 优先使用现有 CLI，不新增平行命令体系。
2. 所有新增脚本必须能在无模型权重、无网络的本地环境下 dry-run 或被单元测试覆盖。
3. 大模型权重、真实 checkpoint、大规模数据和长任务日志不得提交 Git。
4. 修改远程部署逻辑后，必须运行 remote plan 相关测试。
5. 修改 decoder、metrics、data pipeline 后，必须运行对应单元测试。
6. 所有实验输出必须包含 method、prompt id、配置参数和 run 标识。
7. 不允许在测试集上调 verifier 或 decoder 超参后继续把该测试集当最终测试集。

## 本地验收命令

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src python -m ttc_dense_verifier.cli run-local-smoke --output-dir outputs/local_smoke --limit 12
```

## 远程默认入口

远程主机别名：

```text
g3
```

建议远程目录：

```text
/data/lry_machine_learning/ttc_dense_verifier
```

启动远程长任务前必须确认：

```bash
ssh g3 'nvidia-smi && cd /srv/ttc-dense-verifier && git status --short'
```

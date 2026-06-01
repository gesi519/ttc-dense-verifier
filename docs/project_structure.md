# Project Structure

## 1. 结构原则

当前仓库已经具备合理的 Python 包结构和实验配置结构，因此 Harness Engineering 不建议大规模迁移目录。项目结构的重构方向是“固化职责、补充约束、增加自动化入口”，而不是重写现有模块。

## 2. 当前结构职责

```text
ttc-dense-verifier/
  AGENTS.md
  Makefile
  README.md
  pyproject.toml

  configs/
    data_generation/
    evaluation/
    inference/
    training/

  data/
    raw_questions/
    generated_negative/
    generated_positive/
    preference/
    splits/
    evaluation_outputs/
    human_review/

  docs/
    automation_layer.md
    constraints_layer.md
    experiment_protocol.md
    harness_engineering.md
    paper_outline.md
    project_structure.md
    remote_deployment.md
    workflow.md

  src/ttc_dense_verifier/
    data_pipeline/
    decoding/
    demo/
    evaluation/
    inference/
    remote/
    serving/
    training/
    utils/
    workflow/

  scripts/
    local_prepare/
    remote_deploy/
    remote_eval/
    remote_infer/
    remote_train/

  outputs/
    demo_cases/
    figures/
    local_smoke/
    logs/
    tables/

  checkpoints/
    generator_qwen32b_sft_lora/
    verifier_qwen7b_rm/

  tests/
```

## 3. 配置层

`configs/` 是实验参数的唯一可信来源。

- `configs/data_generation/`：问题构造、正样本生成、负样本生成。
- `configs/training/`：Verifier RM 和 Generator SFT baseline 训练。
- `configs/inference/`：Generator、Verifier、Beam TTC、MCTS TTC。
- `configs/evaluation/`：静态指标和 judge prompt。

约束：

- 不在 Python 代码中写死实验参数。
- 长任务启动前必须保存 config snapshot。
- 改动配置后必须能说明影响的实验阶段。

## 4. 数据层

`data/` 保留小样例和结构占位。真实大规模数据不应提交 Git。

- `raw_questions/`：确定性问题集。
- `generated_negative/`：负样本请求和回答。
- `generated_positive/`：正样本请求和回答。
- `preference/`：chosen/rejected 偏好样本。
- `splits/`：固定 split。
- `evaluation_outputs/`：评测输入输出样例。
- `human_review/`：人工评审表。

约束：

- 原始数据、中间生成数据、偏好数据不能混放。
- split 必须按稳定 prompt id 生成。
- 测试集不得参与训练和超参选择。

## 5. 代码层

`src/ttc_dense_verifier/` 按实验阶段划分模块。

- `data_pipeline/`：问题、请求和偏好数据构造。
- `serving/`：远程 generator/verifier 客户端与批处理。
- `decoding/`：Beam Search 和 MCTS。
- `inference/`：标准化推理记录。
- `evaluation/`：指标、报告、图表和 judge 请求。
- `training/`：训练数据导出、输入校验和训练摘要。
- `remote/`：远程 runbook 生成。
- `workflow/`：本地 smoke 和后续端到端编排。

约束：

- 新功能优先接入现有 CLI。
- 模块逻辑必须可单元测试。
- 远程模型调用应通过 client 接口注入，不直接散落在业务逻辑里。

## 6. 自动化层

`Makefile` 是本地 harness 入口：

```bash
make test
make compile
make smoke
make remote-runbook
make verify
```

`scripts/remote_deploy/generated/` 是远程 harness 入口，由 CLI 生成，不应手工维护。

默认 `make verify` 不写入 tracked 样例目录；它会把 smoke 和 runbook 检查输出写到 `/tmp`。

## 7. 输出层

`outputs/` 用于保存小样例、图表和表格。真实长任务输出建议后续迁移到：

```text
runs/<run_id>/
  metadata.json
  configs/
  logs/
  outputs/
  metrics/
  manifests/
```

这可以作为下一轮结构增强，不必在当前提交中一次性搬迁已有输出。

## 8. Checkpoint 层

`checkpoints/` 只保留 `.gitkeep` 或占位结构。

真实 checkpoint 不得提交 Git：

```text
checkpoints/generator_qwen32b_sft_lora/
checkpoints/verifier_qwen7b_rm/
```

远程训练完成后，应通过训练摘要和 manifest 记录 checkpoint 路径，而不是把权重同步回仓库。

# Harness Engineering Plan

## 1. 设计目标

Harness Engineering 层的目标不是替换现有实现，而是把当前仓库已有的数据、训练、推理、评测和远程部署能力组织成可复现的实验系统。

本仓库已有可用模块：

- 数据构造：`ttc_dense_verifier.data_pipeline`
- 解码控制：`ttc_dense_verifier.decoding`
- 推理记录：`ttc_dense_verifier.inference`
- 评测报告：`ttc_dense_verifier.evaluation`
- 训练导出与校验：`ttc_dense_verifier.training`
- 远程 runbook：`ttc_dense_verifier.remote`
- 端到端本地 smoke：`ttc_dense_verifier.workflow.local_smoke`

Harness 层负责统一回答四个问题：

1. 每个阶段由哪个 agent 负责？
2. 每个阶段允许读写哪些目录？
3. 每个阶段的退出条件是什么？
4. 如何用固定命令复现实验？

## 2. 当前进度判断

当前代码已经完成“本地可测 scaffold”阶段：

- 有 CLI 入口和多个子命令。
- 有样例数据与配置文件。
- 有 Beam Search 和 MCTS 的本地实现。
- 有静态质量指标、code guardrail 和论文图表导出。
- 有远程部署 runbook 生成器。
- 有单元测试覆盖主要模块。

尚未完成的是“真实大模型实验闭环”：

- 真实正负样本批量生成。
- 7B verifier 真实训练与验证。
- 32B raw/SFT baseline 的远程推理结果。
- verifier 服务与 TTC 解码的真实联调。
- 三组实验的最终表格与失败案例分析。

## 3. 推荐目录职责

当前目录结构可以保留，不建议大改。建议按职责固化如下：

```text
configs/
  data_generation/      数据生成配置
  training/             LLaMA-Factory 训练配置
  inference/            generator/verifier/TTC 推理配置
  evaluation/           评测指标与 judge 配置

data/
  raw_questions/        原始或确定性构造的问题
  generated_negative/   负样本请求和回答
  generated_positive/   正样本请求和回答
  preference/           chosen/rejected 偏好数据
  splits/               固定 train/val/test split
  evaluation_outputs/   评测输入输出样例
  human_review/         人工审查表

src/ttc_dense_verifier/
  data_pipeline/        数据构造
  serving/              generator/verifier 客户端与批处理
  decoding/             Beam/MCTS TTC
  inference/            推理记录和统一输出
  evaluation/           指标、报告、图表
  training/             RM/SFT 数据导出和训练检查
  remote/               远程 runbook 生成
  workflow/             本地 smoke 和阶段编排

scripts/
  remote_deploy/        远程部署说明与生成脚本输出
  remote_train/         训练说明
  remote_infer/         推理说明
  remote_eval/          评测说明

outputs/
  demo_cases/           小样例和演示输出
  figures/              论文图表源文件
  tables/               指标表格
  logs/                 本地或远程日志占位
```

## 4. Agent 编排

最小闭环顺序：

```text
Data Pipeline Agent
 -> Training Agent
 -> Remote Harness Agent
 -> TTC Inference Agent
 -> Evaluation Agent
 -> Research Lead Agent
```

每个 agent 的详细职责以仓库根目录 `AGENTS.md` 为准。

## 5. 阶段退出条件

### Data

必须存在：

- `data/raw_questions/questions.jsonl`
- `data/generated_positive/positive_generation_requests.jsonl`
- `data/generated_negative/negative_generation_requests.jsonl`
- `data/preference/train.jsonl`
- `data/preference/val.jsonl`
- `data/preference/test.jsonl`

必须通过：

```bash
PYTHONPATH=src python -m unittest tests.test_data_pipeline tests.test_generation_requests -v
```

### Training

必须存在：

- RM dataset export
- SFT dataset export
- `dataset_info.json`
- training config snapshot
- training summary JSON

必须通过：

```bash
PYTHONPATH=src python -m unittest tests.test_training_configs tests.test_training_exports tests.test_training_validation -v
```

### Inference

必须存在：

- raw generator 输出
- SFT baseline 输出
- TTC beam 或 MCTS 输出
- 每条样本的分数和解码参数

必须通过：

```bash
PYTHONPATH=src python -m unittest tests.test_decoding tests.test_inference_decode tests.test_inference_artifacts -v
```

### Evaluation

必须存在：

- 静态指标表
- code guardrail 结果
- judge 请求或结果
- 错误分解
- 论文图表源文件

必须通过：

```bash
PYTHONPATH=src python -m unittest tests.test_evaluation_metrics tests.test_evaluation_reports tests.test_paper_figures -v
```

## 6. 最小执行方式

本地无模型 smoke：

```bash
make test
make smoke
```

默认 smoke 输出写入 `/tmp/ttc-dense-verifier-local-smoke`，避免覆盖仓库内样例输出。

生成远程 runbook：

```bash
make remote-runbook
```

远程执行前检查：

```bash
ssh g3 'nvidia-smi && cd /srv/ttc-dense-verifier && git status --short'
```

## 7. 后续重构建议

优先级从高到低：

1. 给 CLI 增加统一 `--run-id` 和 metadata 输出。
2. 把远程 runbook 的阶段产物清单写成机器可读 manifest。
3. 为 raw baseline、SFT baseline 和 TTC 输出定义同一个 JSONL schema。
4. 增加一个 `workflow run-local-harness` 子命令，串联当前 smoke、评测和图表导出。
5. 增加真实远程 run 的结果目录规范，例如 `runs/<run_id>/metadata.json`。

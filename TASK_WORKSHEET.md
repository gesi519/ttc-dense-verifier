# TTC Dense Verifier 调度工作表

## 0. 调度原则

本工作表用于把完整项目拆成可审计、可提交、可 review 的阶段任务。每个阶段结束时必须满足：

1. 有明确产物。
2. 有本地或远程验证命令。
3. 有阶段总结。
4. 有 Git 提交。
5. 调度器 review 后再进入下一阶段。

调度器职责：

- 维护阶段顺序和依赖。
- 将小任务分配给 `agents/` 下的本地 agent 任务卡。
- 收回 agent 产物后进行代码 review、实验 review 和文档 review。
- 合并通过 review 的改动。
- 每完成一阶段提交到 `main` 并输出阶段总结。
- 对不需要大量 GPU 训练或长时间远程推理的任务，调度器可以新开 agent 一次性完成任务、测试、文档和提交准备，中间无需逐步等待用户确认。
- 对会启动长 GPU 训练、批量远程推理、覆盖 checkpoint、修改远程服务状态或消耗大量预算的任务，调度器必须先停止并等待用户明确确认。

Agent 执行约束：

- 不直接启动长 GPU 任务，除非任务卡明确允许。
- 非长 GPU 任务应尽量一次性完成，完成后把 diff、测试结果、产物和风险统一交回调度器 review。
- 不覆盖已有 checkpoint、真实数据或远程 `.env`。
- 不绕过测试。
- 不把大模型权重、真实训练日志、API key 提交到 Git。
- 所有改动必须在当前仓库目录内完成。

## 0.1 Agent 派发策略

调度器按任务成本分两类处理：

### 一次性 agent 任务

适用范围：

- 文档、schema、contract、报告模板。
- 本地 CLI、测试、Makefile、runbook 生成逻辑。
- 本地 smoke、compile、unit tests。
- 不访问远程服务的 dry-run。
- 只读远程状态检查，且不会启动服务或训练。

执行规则：

1. 调度器选择对应 `agents/*.md` 任务卡。
2. agent 在当前仓库内完成实现、测试和自检。
3. agent 返回修改摘要、验证结果、风险和建议。
4. 调度器 review 后提交。
5. 阶段结束时再向用户汇报。

### 需确认的长任务

适用范围：

- verifier 训练。
- 32B SFT baseline 训练。
- 批量正负样本生成。
- 大规模 baseline 推理。
- TTC beam/MCTS 全量推理。
- 启停远程模型服务。
- 任何可能覆盖 checkpoint、删除数据或消耗大量 GPU 时间的操作。

执行规则：

1. agent 只能先准备脚本、配置和 dry-run 检查。
2. 调度器输出计划、资源影响、预计时间和回滚方式。
3. 用户确认后再执行。

## 1. 总体阶段表

| 阶段 | 名称 | 目标 | 主要负责人 | 是否远程 | 完成状态 |
| --- | --- | --- | --- | --- | --- |
| P0 | Harness 基础层 | 建立 AGENTS、约束层、自动化层 | Scheduler | 否 | 已完成 |
| P1 | 远程路径统一 | 统一 `g3` 项目目录 | Scheduler | 否 | 已完成 |
| P2 | 远程执行入口 | 增加 `remote-*` Makefile 目标 | Scheduler | 否 | 已完成 |
| P3 | 远程 env 校验 | 增加 `.env` 配置检查 | Scheduler | 否 | 已完成 |
| P4 | 远程落地准备 | 同步代码、检查目录、准备 `.env` | Remote Harness Agent | 是，非长任务 | 待执行 |
| P5 | 数据闭环最小化 | 固化问题、生成请求、偏好数据 schema | Data Pipeline Agent | 可本地 | 待执行 |
| P6 | 训练输入闭环 | 导出 RM/SFT 数据并校验训练配置 | Training Agent | 可本地 | 待执行 |
| P7 | 服务健康闭环 | 启动或验证 generator/verifier 服务 | Remote Harness Agent | 是，短任务 | 待执行 |
| P8 | 远程数据生成 | 批量生成正负样本 | Data Pipeline Agent | 是，长任务 | 待执行 |
| P9 | Verifier 训练 | 训练 7B reward verifier | Training Agent | 是，长任务 | 待执行 |
| P10 | Baseline 输出 | 生成 raw/SFT baseline 输出 | Baseline Agent | 是，长任务 | 待执行 |
| P11 | TTC 推理 | 运行 beam/MCTS TTC 输出 | TTC Inference Agent | 是，长任务 | 待执行 |
| P12 | 评测与报告 | 输出指标、表格、失败案例 | Evaluation Agent | 可本地/远程 | 待执行 |
| P13 | 论文材料 | 固化 paper figures、case study、结论边界 | Research Lead Agent | 否 | 待执行 |

## 2. 详细阶段拆解

### P4. 远程落地准备

目标：

- 将当前代码安全同步到 `g3:/data/lry_machine_learning/ttc_dense_verifier`。
- 确认远程目录、GPU、Git 状态和 `.env` 准备情况。
- 不启动 generator/verifier 服务，不启动训练。

任务：

1. 本地确认 `main` 干净。
2. 运行 `make remote-sync`。
3. 运行 `make remote-status`。
4. 在远程复制 `.env.example` 为 `.env`，但不提交 `.env`。
5. 根据实际模型路径和 verifier 服务命令修改远程 `.env`。
6. 运行 `make remote-env-check`。
7. 记录远程状态摘要到 `reports/remote_bootstrap.md`。

验收：

- `make remote-status` 通过。
- `make remote-env-check` 通过。
- `reports/remote_bootstrap.md` 存在，且不含密钥。

提交：

- 提交 `reports/remote_bootstrap.md`，不提交 `.env`。

Review 要点：

- `.env` 未进入 Git。
- 远程路径和本地文档一致。
- 报告不泄露 token、API key 或私有模型访问凭据。

### P5. 数据闭环最小化

目标：

- 确保问题集、生成请求和偏好数据格式完全可复现。
- 先跑最小规模样例，再扩大规模。

任务：

1. 检查 `data/raw_questions/questions.jsonl` 的字段和主题覆盖。
2. 用 CLI 重新生成小规模 questions 到 `/tmp`，比较 schema。
3. 检查 positive/negative generation request prompt 是否符合研究目标。
4. 增加数据 schema 文档到 `docs/data_contract.md`。
5. 如缺少测试，补充数据字段、split 不重叠和空样本过滤测试。
6. 运行数据相关测试。

验收：

- `tests/test_data_pipeline.py` 通过。
- `tests/test_generation_requests.py` 通过。
- `docs/data_contract.md` 存在。
- 数据 split 规则明确。

提交：

- 提交 schema 文档、必要测试、必要小样例更新。

Review 要点：

- `chosen/rejected` 对齐逻辑正确。
- 测试集不进入训练。
- 问题来源、topic、prompt id 可追溯。

### P6. 训练输入闭环

目标：

- 在不启动训练的情况下，确认 RM/SFT 导出和 LLaMA-Factory 配置可用。

任务：

1. 检查 `configs/training/verifier_rm_qwen7b.yaml`。
2. 检查 `configs/training/generator_sft_qwen32b_lora.yaml`。
3. 对样例 preference 数据导出 RM dataset。
4. 对样例 preference 数据导出 SFT dataset。
5. 运行 `validate-training-inputs`。
6. 补充 `docs/training_contract.md`，说明训练前置条件和禁止覆盖 checkpoint。

验收：

- `tests/test_training_configs.py` 通过。
- `tests/test_training_exports.py` 通过。
- `tests/test_training_validation.py` 通过。
- `docs/training_contract.md` 存在。

提交：

- 提交训练 contract、配置修复和测试。

Review 要点：

- 训练输出目录不会覆盖真实 checkpoint。
- dataset_info 与 LLaMA-Factory 约定一致。
- 7B verifier 和 32B SFT baseline 边界清楚。

### P7. 服务健康闭环

目标：

- 在远程确认 generator/verifier 服务可启动、可探测。
- 只做短健康检查，不跑批量数据。

任务：

1. 远程运行 `start_generator_vllm.sh`。
2. 远程运行当前 verifier service 启动命令。
3. 运行 `make remote-health`。
4. 记录 probe JSON 路径。
5. 汇总服务端口、模型名、GPU 分配到 `reports/remote_services.md`。

验收：

- generator probe 通过。
- verifier probe 通过。
- `reports/remote_services.md` 存在。

提交：

- 提交服务报告，不提交日志大文件。

Review 要点：

- endpoint 是 base URL，不重复拼接 `/chat/completions`。
- verifier endpoint 输出标量分数。
- GPU 0-5 / 6-7 分配符合约定。

### P8. 远程数据生成

目标：

- 生成真实正负样本，并构造 preference split。

任务：

1. 运行 prompt expansion。
2. 生成 negative requests。
3. 生成 positive requests。
4. 调用 generator endpoint 生成 negative answers。
5. 调用 generator endpoint 生成 positive answers。
6. 构造 preference split。
7. 生成数据报告。
8. 抽样检查 50 条样本。

验收：

- `data/preference/train_preference.jsonl` 存在。
- `data/preference/val_preference.jsonl` 存在。
- `data/preference/test_prompts.jsonl` 存在。
- 数据报告存在，包含保留/过滤数量。

提交：

- 大规模数据不提交。
- 提交数据报告、抽样审查模板、必要小样例。

Review 要点：

- rejected 是否真实覆盖目标缺陷。
- chosen 是否过度依赖同一模型风格。
- 数据 split 是否稳定。

### P9. Verifier 训练

目标：

- 训练 7B verifier，并完成 post-training score validation。

任务：

1. 导出 RM dataset。
2. 运行训练输入校验。
3. 启动 verifier RM 训练。
4. 导出训练摘要。
5. 切换 verifier 服务到训练后 checkpoint。
6. score validation preference split。
7. 运行 `validate-verifier-scores`。
8. 写 `reports/verifier_training.md`。

验收：

- 训练摘要 JSON 存在。
- pairwise accuracy 达到阈值。
- verifier 服务切换后 probe 通过。

提交：

- 提交训练报告和指标摘要。
- 不提交 checkpoint。

Review 要点：

- loss 和 pairwise accuracy 是否一致。
- 是否存在 chosen/rejected 长度偏置。
- 是否需要增加负样本类型。

### P10. Baseline 输出

目标：

- 生成 raw generator baseline 和 SFT baseline 输出。

任务：

1. 固化 test prompt 快照。
2. 运行 raw generator inference。
3. 如需要，训练/加载 SFT baseline。
4. 运行 SFT baseline inference。
5. 保存输出 manifest。
6. 写 `reports/baselines.md`。

验收：

- raw baseline 输出存在。
- SFT baseline 输出存在或明确标记 skipped with reason。
- 三组实验使用同一 test prompt id。

提交：

- 提交 baseline 报告和小样例。
- 不提交大规模输出。

Review 要点：

- baseline 参数是否公平。
- SFT 是否只是对照组，不成为核心贡献。

### P11. TTC 推理

目标：

- 运行 verifier-guided beam/MCTS 推理，保留 trace 和分数。

任务：

1. 确认 generator/verifier endpoint。
2. 运行 TTC beam。
3. 运行 TTC MCTS。
4. 检查每条输出含 method、prompt id、answer、score、trace。
5. 记录 latency 和 verifier call count。
6. 写 `reports/ttc_inference.md`。

验收：

- TTC beam 输出存在。
- TTC MCTS 输出存在或有明确跳过理由。
- 输出 schema 通过本地校验。

提交：

- 提交推理报告和小样例。

Review 要点：

- 没有丢失分支/score trace。
- beta、beam width、max step 等参数可追溯。

### P12. 评测与报告

目标：

- 对 raw、SFT、TTC 三组输出生成统一指标。

任务：

1. 校验三组 prompt id 一致。
2. 运行 static metrics。
3. 运行 code guardrail。
4. 导出 judge requests。
5. 聚合表格。
6. 抽样失败案例。
7. 写 `reports/eval/main_results.md`。

验收：

- `outputs/tables/` 有核心表格。
- `outputs/figures/` 有论文图表源文件。
- `reports/eval/main_results.md` 存在。
- `reports/eval/failure_cases.md` 存在。

提交：

- 提交报告、表格、小图表源文件。

Review 要点：

- 不只报告有利指标。
- 失败案例是否支持后续改进。
- LLM-as-a-Judge 不是唯一证据。

### P13. 论文材料

目标：

- 将实验结果转化为论文叙事与可复现附录。

任务：

1. 更新 `docs/paper_outline.md`。
2. 写方法图说明。
3. 写实验设置。
4. 写主表格解读。
5. 写消融实验计划。
6. 写局限性。
7. 写复现步骤。

验收：

- paper outline 与真实实验结果一致。
- 不夸大没有跑出的结论。
- 每个结论能指向报告或表格。

提交：

- 提交论文材料文档。

Review 要点：

- 贡献边界是否清楚。
- 控制变量是否严谨。
- 复现路径是否完整。

## 3. Agent 派发表

| Agent | 任务卡 | 可执行阶段 | 主要产物 |
| --- | --- | --- | --- |
| Scheduler | `agents/scheduler.md` | 全部 | 阶段调度、review、提交 |
| Data Pipeline Agent | `agents/data_pipeline_agent.md` | P5, P8 | 数据 contract、数据报告 |
| Training Agent | `agents/training_agent.md` | P6, P9 | 训练 contract、训练报告 |
| Remote Harness Agent | `agents/remote_harness_agent.md` | P4, P7 | 远程 bootstrap、服务报告 |
| Baseline Agent | `agents/baseline_agent.md` | P10 | baseline 报告 |
| TTC Inference Agent | `agents/ttc_inference_agent.md` | P11 | TTC 推理报告 |
| Evaluation Agent | `agents/evaluation_agent.md` | P12 | 评测报告、失败案例 |
| Research Lead Agent | `agents/research_lead_agent.md` | P13 | 论文材料 |

## 4. 调度器 Review 流程

每个 agent 完成任务后提交以下材料：

1. 修改文件列表。
2. 运行命令和结果。
3. 产物路径。
4. 风险和未解决问题。
5. 下一步建议。

调度器 review 清单：

1. 检查 diff 是否只包含任务范围内文件。
2. 检查是否触碰禁止提交的文件。
3. 检查测试是否覆盖变更。
4. 检查文档是否与代码一致。
5. 检查远程命令是否不会意外启动长任务。
6. 必要时要求 agent 返工。
7. 通过后提交到 GitHub。

## 5. 下一步建议

下一步应进入 P4：

```bash
make remote-sync
make remote-status
make remote-env-check
```

然后由 Remote Harness Agent 产出：

```text
reports/remote_bootstrap.md
```

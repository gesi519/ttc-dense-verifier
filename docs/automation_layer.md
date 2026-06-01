# Automation Layer

## 1. 自动化入口

本仓库优先使用现有 CLI：

```bash
PYTHONPATH=src python -m ttc_dense_verifier.cli <command>
```

为减少重复命令，仓库根目录提供 `Makefile` 作为本地 harness 入口。Makefile 不替代 CLI，只组合稳定命令。

## 2. 本地命令

运行全部单元测试：

```bash
make test
```

编译检查：

```bash
make compile
```

本地无模型 smoke：

```bash
make smoke
```

导出远程 runbook：

```bash
make remote-runbook
```

完整本地检查：

```bash
make verify
```

`make smoke` 默认写入 `/tmp/ttc-dense-verifier-local-smoke`。`make verify` 也使用 `/tmp` 下的临时 runbook 目录，避免刷新仓库内 tracked 样例文件。需要更新 `scripts/remote_deploy/generated/` 时，单独运行 `make remote-runbook`。

## 3. 远程部署命令

同步到远程服务器：

```bash
make remote-sync
```

远程启动前状态检查：

```bash
make remote-status
```

远程健康检查：

```bash
make remote-env-check
make remote-health
```

远程长任务：

```bash
make remote-jobs
```

默认远程主机和目录：

```bash
REMOTE_HOST=g3
REMOTE_PROJECT_DIR=/data/lry_machine_learning/ttc_dense_verifier
```

需要覆盖时：

```bash
make remote-sync REMOTE_HOST=g3 REMOTE_PROJECT_DIR=/data/lry_machine_learning/ttc_dense_verifier
```

## 4. 推荐阶段顺序

```text
local verify
 -> export remote runbook
 -> make remote-sync
 -> make remote-status
 -> make remote-env-check
 -> remote health check
 -> data prepare
 -> answer generation
 -> preference split
 -> dataset export
 -> training validation
 -> verifier training
 -> service switch
 -> post-training validation
 -> inference
 -> evaluation
```

## 5. Run 产物要求

每个长任务至少保留：

```text
*.log
*.status
*.config
*.outputs
*.failure   # 仅失败时
```

评测阶段至少保留：

```text
outputs/tables/
outputs/figures/
outputs/demo_cases/
```

## 6. 自动化层后续增强

建议后续新增：

- `runs/<run_id>/metadata.json`
- `runs/<run_id>/manifest.json`
- `runs/<run_id>/configs/`
- `runs/<run_id>/logs/`
- `runs/<run_id>/metrics/`

这样可以把当前远程 runbook 的日志约定提升为完整实验追踪系统。

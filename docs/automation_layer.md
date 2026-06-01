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

同步到远程服务器示例：

```bash
rsync -av \
  --exclude .git \
  --exclude checkpoints \
  --exclude outputs/logs \
  --exclude scripts/remote_deploy/generated/.env \
  ./ g3:/srv/ttc-dense-verifier/
```

远程健康检查：

```bash
ssh g3 'cd /srv/ttc-dense-verifier && set -a && source scripts/remote_deploy/generated/.env && set +a && bash scripts/remote_deploy/generated/health_check.sh'
```

远程长任务：

```bash
ssh g3 'cd /srv/ttc-dense-verifier && set -a && source scripts/remote_deploy/generated/.env && set +a && bash scripts/remote_deploy/generated/run_remote_jobs.sh'
```

## 4. 推荐阶段顺序

```text
local verify
 -> export remote runbook
 -> rsync to g3
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

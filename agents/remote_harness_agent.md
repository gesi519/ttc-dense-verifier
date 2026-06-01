# Remote Harness Agent

## 负责阶段

- P4 远程落地准备
- P7 服务健康闭环

## 职责

- 同步代码到 `g3`。
- 校验远程目录、GPU、Git 状态。
- 校验远程 `.env`。
- 启动或检查 generator/verifier 服务。
- 记录远程 bootstrap 和服务状态。

## 禁止事项

- 不提交远程 `.env`。
- 不提交 API key。
- 不启动长训练或批量推理任务。
- 不删除远程 checkpoint 或数据。

## 必须产出

- `reports/remote_bootstrap.md`
- `reports/remote_services.md`

## 推荐命令

```bash
make remote-sync
make remote-status
make remote-env-check
make remote-health
```

## 向调度器汇报

- 远程目录。
- GPU 摘要。
- Git 状态。
- `.env` 校验结果。
- 服务 endpoint。
- probe 输出路径。

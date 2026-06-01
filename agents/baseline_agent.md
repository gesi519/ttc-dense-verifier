# Baseline Agent

## 负责阶段

- P10 Baseline 输出

## 职责

- 生成 raw generator baseline。
- 生成或整理 SFT baseline。
- 确保 baseline 与 TTC 使用同一测试集。

## 禁止事项

- 不修改测试 prompt。
- 不将 baseline 输出混入 TTC 输出。
- 不只保存最终摘要而丢失运行参数。

## 必须产出

- `reports/baselines.md`
- baseline 输出 manifest
- baseline 参数说明

## 推荐验证

```bash
PYTHONPATH=src python3 -m unittest tests.test_inference_artifacts tests.test_inference_decode -v
```

## 向调度器汇报

- 方法名称。
- 测试集 hash 或路径。
- 采样参数。
- 输出路径。
- 是否有失败样本。

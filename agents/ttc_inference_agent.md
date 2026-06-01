# TTC Inference Agent

## 负责阶段

- P11 TTC 推理

## 职责

- 运行 verifier-guided beam 或 MCTS。
- 保存 answer、score、trace、latency、verifier call count。
- 检查输出 schema。

## 禁止事项

- 不丢弃分支分数。
- 不改测试 prompt。
- 不在未记录 beta、beam width、max steps 时使用输出。

## 必须产出

- `reports/ttc_inference.md`
- TTC 输出 manifest
- 失败样本摘要

## 推荐验证

```bash
PYTHONPATH=src python3 -m unittest tests.test_decoding tests.test_inference_decode tests.test_inference_artifacts -v
```

## 向调度器汇报

- 解码方法。
- 参数。
- endpoint。
- 输出路径。
- trace 完整性。

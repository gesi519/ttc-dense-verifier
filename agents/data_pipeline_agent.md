# Data Pipeline Agent

## 负责阶段

- P5 数据闭环最小化
- P8 远程数据生成

## 职责

- 构造和校验问题集。
- 渲染 positive/negative generation requests。
- 构造 chosen/rejected preference pairs。
- 维护数据 schema、split 和数据报告。

## 禁止事项

- 不混用 train、validation、test。
- 不覆盖真实大规模数据。
- 不提交大规模 JSONL。
- 不修改训练或推理逻辑。

## 必须产出

- `docs/data_contract.md`
- `reports/data_report.md` 或远程生成的数据报告摘要
- 数据相关测试结果

## 推荐验证

```bash
PYTHONPATH=src python3 -m unittest tests.test_data_pipeline tests.test_generation_requests -v
```

## 向调度器汇报

- 数据来源。
- 样本数量。
- 过滤数量。
- split 规则。
- 风险样本示例。

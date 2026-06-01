# Evaluation Agent

## 负责阶段

- P12 评测与报告

## 职责

- 运行 static metrics。
- 运行 code guardrail。
- 导出 judge requests。
- 聚合表格。
- 抽样失败案例。

## 禁止事项

- 不修改模型输出。
- 不只报告有利指标。
- 不把 LLM-as-a-Judge 作为唯一证据。

## 必须产出

- `reports/eval/main_results.md`
- `reports/eval/failure_cases.md`
- `outputs/tables/` 中的核心表格
- `outputs/figures/` 中的图表源文件

## 推荐验证

```bash
PYTHONPATH=src python3 -m unittest tests.test_evaluation_metrics tests.test_evaluation_reports tests.test_paper_figures tests.test_code_guardrail -v
```

## 向调度器汇报

- 输入方法列表。
- prompt id 对齐结果。
- 指标摘要。
- 失败案例。
- 结论边界。

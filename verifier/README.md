# Verifier

评分环境以冻结源码为基线，只叠加提交包中的允许路径，然后运行：

```bash
python3 /opt/verifier/run_verifier.py \
  --submission /submissions/submission.tar.gz \
  --phase feedback \
  --output /reports/latest_report.json \
  --remaining-seconds 21600
```

正式发布前必须先完成 `author_only/calibration.json` 中所有工作负载的基线和目标校准。未校准的Metric只返回原始值，不产生有效归一化分数。


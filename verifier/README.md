# Verifier

评分环境以冻结源码为基线，按提交Manifest完整替换 `src/main/`，并始终使用Judge持有的POM和测试：

Verifier控制进程以root身份读取评分材料，Maven及候选代码则降权为 `judge-runner`。
评分材料和报告目录对该用户不可读。

```bash
python3 /opt/verifier/run_verifier.py \
  --submission /submissions/submission.tar.gz \
  --phase feedback \
  --output /reports/latest_report.json \
  --remaining-seconds 21600
```

任务结束后按可信账本中的最佳Artifact执行Final评测：

```bash
python3 /opt/verifier/run_verifier.py \
  --evaluate-best \
  --phase final \
  --output /reports/final_report.json
```

正式发布前必须先完成 `author_only/calibration.json` 中所有指标的基线和目标校准。未校准任务会触发Hard Gate，正式得分为0。

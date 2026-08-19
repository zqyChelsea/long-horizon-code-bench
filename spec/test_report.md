# Test Report字段

每次有效评测至少返回：

- `score_current`：当前产物得分 `S_t`；
- `score_best`：历史最佳得分 `S_best`；
- `reward_delta`：本轮增量 `R_t`；
- `test_groups`：各测试组通过数和总数；
- `metrics`：各性能组当前值、方向和归一化分数；
- `new_regressions`：相对上一有效提交新增的失败；
- `hard_gate`：硬门槛状态；
- `remaining_seconds`：剩余任务预算；
- `integrity_violations`：完整性违规。

轨迹指标用于最终Benchmark分析，不直接计入 `S_t` 或 `R_t`。


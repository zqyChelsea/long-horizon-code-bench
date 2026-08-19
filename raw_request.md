# 原始任务来源

## 真实软件问题

`exchange-core` 是基于 LMAX Disruptor 的开源交易撮合引擎。项目内置多种吞吐测试，覆盖单交易对、现货、保证金、多交易对和大规模账户负载。真实工程问题是：在保持撮合结果、账户余额、风险检查及状态确定性的前提下，提高固定硬件上的综合吞吐量。

## 参考任务

EdgeBench 的公开任务 `exchange_core_throughput` 要求 Agent 优化 `PerfThroughput#testThroughputPeak`，并使用正确性断言和 MT/s 结果进行评分。本任务保留其真实代码库和连续性能 Reward 思路，并扩展为多工作负载、分层测试和12小时反馈闭环。

## 来源链接

- 代码库：<https://github.com/exchange-core/exchange-core>
- 冻结提交：<https://github.com/exchange-core/exchange-core/commit/2f8548749839e9095c8dc597e4b61521d259fa5d>
- 官方吞吐测试：<https://github.com/exchange-core/exchange-core/blob/2f8548749839e9095c8dc597e4b61521d259fa5d/src/test/java/exchange/core2/tests/perf/PerfThroughput.java>
- EdgeBench：<https://github.com/ByteDance-Seed/EdgeBench>


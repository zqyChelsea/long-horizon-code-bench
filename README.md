# exchange-core 长程吞吐优化任务

本目录实现一个基于真实开源项目
[`exchange-core`](https://github.com/exchange-core/exchange-core) 的长程 Code Agent
评测任务。任务要求 Agent 在保持撮合、风险控制和账户状态正确的前提下，持续优化多种交易负载下的吞吐量。

## 来源

- 上游仓库：<https://github.com/exchange-core/exchange-core>
- 冻结提交：`2f8548749839e9095c8dc597e4b61521d259fa5d`
- 原始吞吐测试：`src/test/java/exchange/core2/tests/perf/PerfThroughput.java`
- 参考任务：EdgeBench `exchange_core_throughput`
- 上游许可证：Apache License 2.0，见 `workspace/exchange-core/LICENSE.txt`

## 目录

```text
exchange_core_throughput_long/
├── raw_request.md                 # 真实来源与原始任务记录
├── qualification.md               # 长程资格审查
├── source_metadata.yaml           # 冻结源码元数据
├── task/                          # Agent可见任务说明
├── spec/                          # Agent可见评测约定
├── workspace/exchange-core/       # 作者侧冻结源码快照
├── public_tests/                  # Agent可见公开测试入口
├── submission/                    # 产物打包工具
├── environment/                   # 工作与评分镜像
├── verifier/                      # Agent不可见评分逻辑
├── author_only/                   # Requirement、Oracle与隐藏数据
├── scripts/                       # 任务包质检工具
└── pilot_report.md                # 2/6/12/24小时试运行记录
```

## 快速检查

```bash
python3 scripts/validate_package.py
python3 -m unittest discover -s scripts/tests -v
```

## 构建镜像

在本目录下执行：

```bash
docker build -f environment/work/Dockerfile -t exchange-core-long-work .
docker build -f environment/judge/Dockerfile -t exchange-core-long-judge .
```

正式评测必须使用固定、独占或严格隔离的 Linux AMD64 计算节点。共享机器上的吞吐结果不能用于正式排名。


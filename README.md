# exchange-core 长程性能优化任务

本目录实现一个基于真实开源项目
[`exchange-core`](https://github.com/exchange-core/exchange-core) 的长程 Code Agent
评测任务。Agent需要在12小时内持续优化交易撮合引擎，同时保持撮合、风险控制、
账户、状态和公开接口行为正确。

## 一、任务来源与当前状态

- 上游仓库：<https://github.com/exchange-core/exchange-core>
- 冻结提交：`2f8548749839e9095c8dc597e4b61521d259fa5d`
- 原始性能测试：`src/test/java/exchange/core2/tests/perf/PerfThroughput.java`
- 参考任务：EdgeBench `exchange_core_throughput`
- 运行预算：12小时
- 固定环境：Linux AMD64、12核CPU、32 GiB内存、Java 17、禁止联网

冻结源码包含159个文件，已与上游冻结提交逐路径、逐内容核对一致。当前任务包属于
**结构完整但尚未发布就绪的Draft**：性能Floor/Target、Oracle、Docker运行、重复评分和
2/6/12/24小时Pilot仍需在固定Linux节点上完成。状态以
`author_only/release_status.json` 为准。

## 二、任务的整体结构

任务由五个相互隔离的层次组成：

| 层次 | 作用 | Agent可见性 |
|---|---|---|
| 任务定义层 | 提供英文任务目标、约束和公开评测约定 | 可见、只读 |
| 工作层 | 提供冻结源码和公开测试，Agent只修改 `src/main/` | 可见，限定编辑 |
| 提交层 | 生成完整源码树、逐文件哈希和不可变提交包 | 工具可调用 |
| 评分层 | 使用Judge持有的POM、隐藏测试、Metric和完整性检查评分 | 不可见 |
| 作者质检层 | 保存Requirement、Oracle、校准值和发布状态 | 不可见 |

```text
Agent读取task/spec
        ↓
修改workspace/exchange-core/src/main
        ↓
运行公开测试并提交完整源码树
        ↓
Judge复制冻结baseline并替换整个src/main
        ↓
使用Judge POM安装隐藏测试并执行Test Case/Metric
        ↓
返回Test Report，Agent继续迭代
        ↓
保存最佳有效Artifact，任务结束后运行Final Held-out评测
```

## 三、目录说明

```text
exchange_core_throughput_long/
├── raw_request.md                  # 原始工程问题和参考任务来源
├── qualification.md                # 长程任务资格与Pilot准入门槛
├── source_metadata.yaml            # 上游提交、运行资源和源码摘要
├── task/task.md                    # Agent可见的英文任务Prompt
├── spec/                            # Agent可见的评分与反馈边界
├── workspace/exchange-core/         # 完整的冻结上游源码，无Git历史
├── public_tests/                    # Agent可见的公开测试入口
├── policy/                          # 工具白名单、命令网关和轨迹策略
├── submission/                      # 完整源码树打包与Manifest生成
├── environment/                     # 断网的Work/Judge双容器定义
├── verifier/
│   ├── run_verifier.py              # Test、Metric、Hard Gate及Report
│   ├── artifact_registry.py         # 提交账本与最佳Artifact管理
│   ├── integrity_check.py           # 产物与轨迹完整性检查
│   ├── scoring.yaml                 # Test权重和硬门槛
│   └── workloads/                   # Feedback/Final性能工作负载
├── author_only/
│   ├── requirements.yaml            # Requirement到Verifier的映射
│   ├── calibration.json             # 固定硬件上的Floor和Target
│   ├── release_status.json           # 正式发布所需质检状态
│   ├── hidden_tests/                 # Feedback和Final隐藏测试
│   └── oracle_solution/              # Oracle候选、构建规则和验证说明
├── scripts/                          # Draft/Release校验及单元测试
└── pilot_report.md                   # 校准与长程Pilot结果
```

Agent只访问任务说明、公开规范、工作区、公开测试、提交工具和最新反馈；Verifier、
`author_only/`、Git历史、隐藏测试、Oracle及最佳产物仓库不得进入Agent工作区。

## 四、评分和反馈

### 4.1 Test Case

构建、撮合、风险、账户、状态、兼容和异常路径均由Judge控制的测试执行。每条测试为
0/1；只有退出码为0、预期JUnit报告存在、预期测试类实际执行且无失败、错误或跳过时，
测试组才完整通过。没有JUnit报告不能根据Maven退出码推定为通过。

### 4.2 Metric

当前多维性能分包括：

```text
S_metric =
    0.65 × 综合吞吐
  + 0.20 × P99延迟
  + 0.10 × CPU处理效率
  + 0.05 × 峰值内存
```

各指标在固定硬件上根据Floor和Target归一化至 `[0,1]`。所有配置权重始终进入分母；
失败、超时、报告缺失或无效结果记0，不能通过删除无效指标抬高分数。
吞吐得分由Judge根据固定交易数量和外部计时计算；程序自身打印的 `Average: ... MT/s`
仅作为诊断值，不能直接决定得分。

### 4.3 正式得分与诊断分

```text
score_progress = 0.3 × S_test + 0.7 × S_metric

S_t = score_progress，前提是全部Hard Gate通过；
S_t = 0，若任一Hard Gate失败。

R_t = S_t - S_(t-1)
```

`score_progress`只用于反馈部分进展，不进入正式Reward，也不能成为最佳产物。构建失败、
强制测试失败、测试协议失败、Metric协议失败、校准缺失或完整性违规均属于Hard Gate。

## 五、提交、重建和最佳产物

提交工具只收集完整 `src/main/`，并生成 `submission_manifest.json`，其中包含基线提交、
文件路径、大小、SHA-256和源码树摘要。Judge不会把提交简单覆盖到baseline，而是先删除
baseline的整个 `src/main/`，再根据Manifest重建，因此删除和重命名操作不会丢失。

`pom.xml`、`.mvn/`、测试和构建插件均由Judge持有，Agent版本不会进入评分环境。
Verifier以root身份准备只读输入，但所有候选代码和Maven测试均降权到独立的
`judge-runner` 用户执行；该用户不能读取 `/opt/verifier`、`/opt/author_only`、
`/opt/baseline` 或 `/reports`。

每轮评测写入可信的 `history.jsonl`，记录Artifact哈希、报告哈希、得分、阶段和有效性。
只有有效且得分更高的提交会保存到内容寻址的Artifact仓库并原子更新 `best.json`。
Final评测根据 `best.json` 的哈希重新取得并校验Artifact，不依赖单独的 `score_best` 数字。

## 六、Oracle的含义和来源

Oracle是作者侧证明任务可完成的有效实现，不是唯一正确答案，也不是Verifier本身。

- PR/Issue任务可使用经复核的上游合并PR或目标提交；
- 原创需求由任务作者独立实现，并由另一名工程师审核；
- 性能任务需要在冻结硬件上稳定优于基线且通过全部正确性测试；
- 黑盒重建任务使用原程序的可观察行为和隐藏行为测试；
- 迁移任务使用可成功迁移的目标版本和兼容性测试。

当前 `oracle.patch` 只是候选优化，尚不能作为正式Target。Oracle必须稳定通过全部强制测试，
至少重复测量5次，并同时验证No-op失败及不同结构的正确实现不会被误拒。完整规则见
`author_only/oracle_solution/CONSTRUCTION.md`。

## 七、已发现的七项问题及修复

| 问题 | 审计结论 | 当前修复 |
|---|---|---|
| 1. 代码或任务包不完整 | 冻结源码完整，但校准、Oracle和Pilot未完成；原校验只验证静态结构 | 增加Draft/Release两级校验和机器可读发布状态；Release模式下任一校准或质检缺失均失败 |
| 2. Oracle来源不明确 | 当前Oracle由任务作者编写，并非上游自带，且尚未验证 | 增加多类数据源的Oracle构建规则、重复实验、No-op、替代实现和独立审核要求 |
| 3. Agent可利用`pom.xml`影响Judge | 原提交允许POM，Judge又按候选POM运行测试，存在跳过或重定向测试风险 | 提交仅允许完整`src/main/`；Judge固定使用baseline POM、Maven配置、插件和测试目录 |
| 4. 测试、Metric及Hard Gate可错误计分 | 无JUnit报告可能判通过，无效Metric会缩小分母，Hard Gate失败仍可能保留分数 | 预期报告缺失记失败；Metric使用固定分母；Hard Gate失败使正式分归零且禁止更新最佳产物 |
| 5. 只优化吞吐可能牺牲其他质量 | 单一吞吐目标可能恶化尾延迟、CPU效率和内存 | 加入P99延迟、CPU处理效率和峰值RSS，并在固定环境中统一校准 |
| 6. 覆盖式提交丢失删除语义 | 只归档现存文件会使baseline旧文件在Judge中残留 | 提交完整源码树和Manifest；Judge先删除旧`src/main/`再重建候选树 |
| 7. `score_best`未绑定最佳产物 | 原逻辑只维护数字，无法证明最终评测对应哪个提交 | 增加内容寻址Artifact仓库、追加式历史账本、原子`best.json`和Final摘要复核 |

## 八、校验与运行

### Draft结构校验

```bash
python3 scripts/validate_package.py --mode draft
python3 -m unittest discover -s scripts/tests -v
```

### Release准入校验

```bash
python3 scripts/validate_package.py --mode release
```

当前Release校验应失败，这是预期行为；不得通过手工填写状态绕过校准和Pilot证据。

### 构建容器

```bash
docker build -f environment/work/Dockerfile -t exchange-core-long-work .
docker build -f environment/judge/Dockerfile -t exchange-core-long-judge .
```

正式评测必须使用固定、独占或严格隔离的Linux AMD64节点。共享机器或macOS上的性能结果
只能用于开发调试，不能用于填写正式Floor、Target或排行榜分数。

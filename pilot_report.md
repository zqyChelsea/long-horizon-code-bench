# Pilot Report

## 当前状态

- [x] 冻结真实源码与提交版本
- [x] 构建英文任务Prompt和公开评测约定
- [x] 构建工作/评分双环境定义
- [x] 构建Test Case、Metric、Reward和Test Report逻辑
- [x] 构建反馈与最终隐藏性能测试
- [x] 构建工具白名单、命令网关、轨迹审计与提交完整性检查
- [ ] 在固定Linux AMD64机器上构建两个Docker镜像
- [ ] 重复运行冻结基线并填写所有 `floor`
- [ ] 验证Oracle并填写所有 `target`
- [ ] 执行Oracle、No-op、错误产物与不同正确实现质检
- [ ] 运行2/6/12/24小时多Agent试验
- [ ] 完成长程有效性和Verifier稳定性审核

## 校准记录

| 阶段 | 工作负载 | Floor中位数 | Target中位数 | 变异系数 | 状态 |
|---|---|---:|---:|---:|---|
| Feedback | peak_multisymbol |  |  |  | 待运行 |
| Feedback | margin_single_symbol |  |  |  | 待运行 |
| Feedback | exchange_single_symbol |  |  |  | 待运行 |
| Feedback | medium_multisymbol |  |  |  | 待运行 |
| Final | peak_multisymbol |  |  |  | 待运行 |
| Final | margin_single_symbol |  |  |  | 待运行 |
| Final | exchange_single_symbol |  |  |  | 待运行 |
| Final | medium_multisymbol |  |  |  | 待运行 |

## Agent长程试运行

| Agent | 2h Best | 6h Best | 12h Best | 24h Best | 6→12h提升 | 12→24h提升 |
|---|---:|---:|---:|---:|---:|---:|
| Agent A |  |  |  |  |  |  |
| Agent B |  |  |  |  |  |  |
| Agent C |  |  |  |  |  |  |

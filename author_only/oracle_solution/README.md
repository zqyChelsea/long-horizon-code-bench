# Oracle候选

Oracle用于证明任务存在可验证的性能提升路径，不代表唯一正确实现，也不向Agent公开。

当前目录提供一个最小候选补丁，调整吞吐配置中的引擎数量和消息分组上限。正式发布前应：

1. 在固定硬件上应用补丁；
2. 运行全部Mandatory Test Case；
3. 分别运行反馈和最终工作负载至少5次；
4. 将中位数写入 `author_only/calibration.json` 的 `target`；
5. 若补丁未稳定优于基线，继续人工优化或更换Oracle；
6. Oracle补丁不得进入Agent工作镜像。


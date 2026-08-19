# Agent工具与防投机策略

正式运行器必须采用默认拒绝策略，只向Agent暴露 `agent_tools.yaml` 中列出的文件工具和命令网关，不能同时开放原始Shell、浏览器、网页搜索、远程代码托管平台或外部MCP。

`command_gateway.py` 对命令进行白名单校验、清理环境变量，并将允许及拒绝的调用记录为JSONL。它应由可信运行器以受控身份调用，再将命令子进程降权为 `agent` 用户；轨迹日志由Agent不可写的独立卷保存，并在评分时通过 `--trajectory-log` 交给Verifier。

命令网关不能代替系统级断网。正式评测仍必须使用 `network_mode: none`、Linux网络命名空间或等效虚拟机隔离；仅使用命令过滤器的本机试跑只能标记为开发验证。

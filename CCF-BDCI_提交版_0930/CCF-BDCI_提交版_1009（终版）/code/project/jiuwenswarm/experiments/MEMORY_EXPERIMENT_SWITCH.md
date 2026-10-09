# Code Agent 记忆 Rail 实验开关

在 JiuwenSwarm 的用户配置 `~/.jiuwenswarm/config/config.yaml` 中设置 `modes.code.memory.experiment_group`。同一份配置复制为两份，只修改这一行，分别启动 Code Agent 运行实验：

```yaml
modes:
  code:
    memory:
      enabled: true
      experiment_group: baseline  # ProjectMemoryRail
```

增强组改为 `experiment_group: enhanced`，挂载 `EnhancedMemoryRail`。省略该字段时默认 `baseline`；其他值会报错。开关同时用于单 Code Agent 和 Code Team（leader、teammate）。普通 Chat Agent 不使用此开关。`models`、工具、其他 Rails、任务输入与运行参数应在两组配置中保持一致。

目前两种 Rail 的记忆来源不同：`ProjectMemoryRail` 读取项目记忆文件，`EnhancedMemoryRail` 在当前进程内写入并检索对话记忆。正式对比前需准备相同的实验事实与任务，并记录两组实际可访问的记忆；增强 Rail 尚不持久化 L1 记忆，重启 Agent 会清空。

自动化的记忆问答对照实验见 [AGENT_MEMORY_AB.md](AGENT_MEMORY_AB.md)。运行器在内存中切换两组，不会改写用户的 `config.yaml`。

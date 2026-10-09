# 提交代码入口

先读 [运行指南](run_guide.md)。`main.py replay` 使用保存的真实实验与审阅后正文离线重建候选论文；`live` 调用 DashScope qwen3.8-max，`image` 调用百炼 qwen-image-3.0-pro。`experiment` 单独运行 DeepAgent 对照实验。

默认写作与图像配置在 `config.yaml`，实验配置在 `config.experiment.yaml`。只引用环境变量，不含任何团队密钥。

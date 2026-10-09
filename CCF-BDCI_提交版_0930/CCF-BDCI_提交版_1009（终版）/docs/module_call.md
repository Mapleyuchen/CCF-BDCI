# 模块调用与 openJiuwen 集成

`code/main.py replay` → generate_framework.py → fill_content.py → evidence.py / prose.py / research_assets.py → LaTeX / BibTeX → paper_quality/checker.py。

`live` → write_paper.py → JsonModel.complete → DashScope 兼容 chat/completions。`editorial.py` 保存四阶段响应，可在输入一致时复用已完成阶段。`image` → generate_methodology.py → 百炼异步 image-generation → tasks 查询 → 下载 PNG。两者使用 DASHSCOPE_API_KEY，但接口路径不同。arXiv 使用独立的公开 HTTPS Atom 接口，无需 Key。

`experiment` → longmemeval_turn20_ab.py → agent_memory_ab.py → openJiuwen DeepAgent → ProjectMemoryRail / EnhancedMemoryRail。增强 Rail 的 before/after hooks 将过程内 L1 记忆注入真实模型请求并记录已完成交换；当前实验不经过 L2/L3 持久化或团队同步。模型数据只来自记录，self-test 模型不进入论文。

具体参数见 code/run_guide.md 和源码内 references/api_workflow.md。比赛机器需提供自有同地域 API Key、Python 环境与 LaTeX；不需要本机绝对路径、Codex 服务或模型权重。

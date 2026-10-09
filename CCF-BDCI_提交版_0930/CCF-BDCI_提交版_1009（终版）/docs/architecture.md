# 系统架构

系统分为实验层、证据层和论文层。实验层通过 openJiuwen DeepAgent 对比 ProjectMemoryRail 与 EnhancedMemoryRail，分别执行直接文件写入和模型驱动的 L1 写入；查询使用独立 conversation ID，审计实际提示词中的记忆。

证据层保留原始 records/runs、数据哈希及模型身份。按题目 ID 匹配有效记录，重算准确率、完整事实召回、配对结果、Wilson 描述性区间、查询/写入成本以及每个正确答案的总成本。失效或缺失 usage 不会伪装成零。

论文层由 arXiv 元数据、研究 brief 和实验快照生成规则框架，再调用 qwen3.8-max 规划、初稿、审阅和修订。段落采用已知数值/引用标记，程序负责解析、LaTeX 和 BibTeX。方法示意图由百炼 qwen-image-3.0-pro 生成，实测图表由 Matplotlib 绘制。

输出包括正文、公式、诊断附录、引用映射、模型阶段记录及来源哈希。CLI 尚未注册为主聊天 Agent 工具。机械检查与真实学术审阅、比赛材料完整性分开报告。

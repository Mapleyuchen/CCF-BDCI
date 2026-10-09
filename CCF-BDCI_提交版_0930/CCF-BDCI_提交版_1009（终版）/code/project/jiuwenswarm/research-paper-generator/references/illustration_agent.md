# 研究内容驱动的配图 Agent

全部代码位于 `research-paper-generator/`，入口是 `scripts/write_paper.py` 与 `scripts/generate_illustrations.py`，实现位于 `scripts/paper_illustration/`。不改 JiuwenSwarm 核心和首页 README。

## 默认流程：一次细致规划，直接生成

1. 从 brief、方法说明、已核验实验快照建立来源目录，保存证据哈希。只向配图模型发送机制材料，不重复发送实验统计。
2. 一次 `qwen3.8-max` 请求同时完成研究理解、互补图设计及每图最终英文提示词。记录目的、来源、节点、连线、图注和正文解释目标。
3. 每图至多七个节点、一个分区、无环结构；细节放图注。提示词明确空间位置、所有连线、短标签白名单与科研图形，目标不超过 320 词，禁止小字段落和虚构结果。
4. 程序校验来源 ID、节点/边、无环结构和标签；每张图只提交一个 `qwen-image-3.0-pro` 任务，多图并行。默认不调用设计审阅、视觉审阅或重绘。
5. 一次正文请求完成论文。正文必须使用 `[[figure:ID]]` 引用并解释每张图；数字、引用和 LaTeX 由代码验证和渲染。只有实际格式错误才最多追加一次定向修复，不做常规全文模型复审。

两图成功路径是 **两次文本请求、两个并行图像任务**。配图规划最多 6500 输出 Token，正文最多 14000；关闭 thinking。实际耗时和 API 返回 usage 写入清单与 `content_report.json`，包括缓存标记；不把输出上限当实际消耗，不把传输重试遗漏的 usage 当完整账单。

默认清单标记 `generated_unreviewed`、`model_visual_review: not_requested`，不将代码检查冒充科学审阅。实测图表仍由 Matplotlib 根据已有记录绘制，不新增研究实验。

## 运行与恢复

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --generate-illustrations --output output/paper-new --compile
```

模型与地域在 `examples/dashscope-research.yaml` 配置，使用 `DASHSCOPE_API_KEY`。`--generate-methodology` 是兼容别名，`--max-figures` 范围 1–4。无 Torch、CUDA 或本地模型权重依赖。

恢复图片阶段时输入、模型与图像设置必须一致，并使用新目录：

```powershell
python jiuwenswarm/research-paper-generator/scripts/generate_illustrations.py output/paper-new/framework --resume-from output/paper-new/illustrations --output output/images-recovered
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --illustration-manifest output/images-recovered/manifest.json --output output/paper-recovered --compile
```

已完成图片按哈希复用；已有任务 ID 只继续查询原任务；创建请求没有返回任务 ID 时不会自动重提。缓存文本调用标注 `reused_from_previous_run`，不重复计入本轮 Token。

完整离线重排，无需密钥：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --content-json output/paper-new/paper/content.json --illustration-manifest output/paper-new/paper/illustrations/manifest.json --output output/paper-replay --compile
```

`paper/illustrations/` 自带完整输入、设计、提示词、PNG、任务来源与哈希，复制后可独立使用。框架目录须完整携带其证据快照。

## 可选深度审阅

仅显式设置 `--review-mode reviewed` 才启用分析、设计审阅、视觉审阅，以及正文规划/草稿/审阅/修订。默认仍不重绘；加 `--max-redraws 1` 或 `2` 才允许相应额外图像任务。它成本较高，不用于默认演示。内部简化重设计也默认关闭。

深度写作恢复使用 `--review-mode reviewed --resume-from <old-run>/paper`；不能混用 fast 和 reviewed 的图像阶段缓存。底层 `generate_methodology.py --prompt ...` 保留为独立图像接口调试入口。

## 边界

代码检查不证明像素中的箭头和文字完全正确。所有模式保留 `human_review_required: true`，最终 PDF 需按实际尺寸查看。配图设计独立于固定的记忆研究提示词，但整篇研究 profile 的公式和数据适配器仍有 L1 研究专用部分。

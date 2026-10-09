# 资源消耗报告

源码版本 `e0fa45cfa18d6a71a6bcd90c4a22592fc1e4adbb`。实验模型为 qwen-plus（受控实验为 qwen-plus-2025-12-01，评分模型 qwen3-max-2026-01-23），写作模型为 qwen3.8-max，图像模型为 qwen-image-3.0-pro。本轮没有重新运行历史实验；归一化记录在 evidence/normalized_results.json，受控实验记录在 evidence/…/memory_eval_v2 对应的源码目录中。

## 实验记录

两种预算共享二十道问题；每预算基线与增强各二十次查询，增强另有四百次记忆写入。六百字符预算基线 4,686 Token、增强 101,669 Token；两千四百字符预算基线 16,877 Token、增强 264,036 Token，合计 387,268 Token。增强总成本包含写入，不能只比较 query_tokens。

## 本轮写作与图像

| 阶段 | 输入 Token | 输出 Token | 总 Token | 请求累计秒 | HTTP 尝试 |
| --- | --- | --- | --- | --- | --- |
| editorial_plan | 14,707 | 5,290 | 19,997 | 227.282 | 2 |
| editorial_draft | 19,770 | 6,314 | 26,084 | 493.468 | 3 |
| editorial_review | 20,381 | 1,163 | 21,544 | 30.438 | 1 |
| editorial_revision | 22,361 | 6,303 | 28,664 | 242.015 | 2 |
| schema_repair | 21,948 | 6,390 | 28,338 | 131.656 | 1 |

已返回 usage 的五次写作响应合计 124,627 Token。规划和初稿是在恢复运行中复用的旧阶段，只计一次。首次审阅的连接失败以及没有取得响应的尝试缺少 usage，因此这个合计不是完整计费账单。独立写作模型连通性探测记录在 evidence/writing_model_probe.json。

四阶段修订完成后，自动格式修复仍未通过严格数字校验。最终稿由保存的 revision 经过 Codex 对照记录编辑，再离线编译；原始失败报告未隐藏，见 writing_run/raw_model_report.json。最终离线重排没有新增模型调用。

百炼图像 API 成功生成两张图，每次 n=1，分辨率 2688×1536。首图一条成本箭头不完整，第二张修订提示词后采用；两次任务及 usage 均在 evidence/image_runs。不是本地模型生成，也没有将 Codex 内置图片当作 API 成果。未测实际账单金额、CPU 峰值、完整流程墙钟时间；不填估算费用。

最终 PDF 二十四页。上文 75 项机械检查与 58 项源码单元测试是本机在旧版十一页稿上记录的历史结果，未在扩充稿上重跑；扩充稿仅经 LaTeX 编译通过、无未定义引用校验。页面已逐页检查，实验仍需人工科学复核。本机使用 Windows、Python 3.11、Matplotlib、LaTeX，无 Torch/CUDA 推理。

# 提交包运行指南

在提交目录根部执行。Python 3.11；PDF 需要系统 LaTeX 的 pdflatex、bibtex、ICLR 所用标准包及 placeins。论文流程不需要 Torch、CUDA、本地模型权重或 Codex。

```powershell
conda env create -f code/environment.yml
conda activate ccf-bdci-submission
python code/main.py replay --output ../paper-replay-new
```

已有兼容环境时可 `python -m pip install -r code/requirements.txt`。离线复现不调用 API，正文取自 `evidence/writing_run/content.json`；没有 LaTeX 时加 `--no-compile`。所有运行输出须位于提交目录外，且输出路径不存在。

## 在线调用

设置与北京地域匹配的 `DASHSCOPE_API_KEY`；也可将密钥放在提交包外的 private.env，使用 `--env-file ../private.env`。使用自己的账号额度，不随材料交付密钥。

```powershell
python code/main.py image --output ../methodology-new
python code/main.py live --generate-methodology --output ../paper-live-new
```

图像采用百炼原生异步接口，保存 task ID、usage 和图像哈希。文本默认 qwen3.8-max；不带 `--generate-methodology` 的 live 模式复用已检查的配图。不会调用 OpenAI 服务。模型输出仍可能触发证据/数字校验失败，此时保留正文和阶段记录，可复核后离线重排；不能绕过校验宣称模型已生成合格论文。当前提交稿经过额外的 Codex 证据与语言编辑，记录见 `evidence/writing_run/editorial_corrections.json`，并未冒充人工学术认可。

API 路由、arXiv 配置及任务恢复命令见 `code/project/jiuwenswarm/research-paper-generator/references/api_workflow.md`。其中仓库根目录命令在 `code/project/` 下执行；本指南的 `main.py` 命令在提交根目录执行。arXiv 无需 Key。

## Agent 实验与验证

```powershell
python -m pip install -e ./code/project/jiuwenswarm
python code/main.py experiment --self-test --max-cases 1 --output ../agent-self-test
python code/main.py experiment --max-cases 0 --context-chars 600 --output ../agent-live-600
python code/main.py test
python code/main.py verify
```

真实实验会产生模型费用；self-test 只验证路径，不能用作论文证据。Windows 首次初始化曾出现上游文件锁日志，仍需跨平台复核。模型实验与论文写作独立：重写论文不会重新执行已保存的 qwen-plus 实验。

更改材料后运行 `python code/main.py manifest`，再运行 verify。缺少队伍名、最终 PDF 的 Reviewer Token、上游 PR 或人工复核时 verify 会如实失败，这不是 API 或离线论文流程失败。

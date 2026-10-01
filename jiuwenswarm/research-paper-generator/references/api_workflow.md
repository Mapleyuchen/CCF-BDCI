# 论文与 API 调用说明

配置入口是 `examples/dashscope-research.yaml`。文本与方法图均使用阿里云百炼，读取 `DASHSCOPE_API_KEY`；当前流程不调用 OpenAI 服务。密钥、接口域名和模型须属于同一地域。以下命令在仓库根目录执行。

## 环境与凭据

```powershell
conda env create -f jiuwenswarm/research-paper-generator/environment.yml
conda activate ccf-bdci
```

已有 `ccf-bdci` 环境直接激活即可。论文流程只需 Python 3.11、Matplotlib、PyYAML、python-dotenv；HTTP 请求使用标准库，不需要 Torch、CUDA、图像模型权重或 Codex 安装。编译 PDF 另需 PATH 中的 `pdflatex` 和 `bibtex`。运行真实 DeepAgent 实验才需要 `python -m pip install -e ./jiuwenswarm`。

密钥可以保存在 Windows 用户环境变量 `DASHSCOPE_API_KEY` 中，新开的终端继承该变量。若当前 IDE 启动早于配置时间，可在它的 PowerShell 终端刷新：

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY', 'User')
```

也可以使用仓库和提交包之外的私有 env 文件，运行时加 `--env-file <路径>`。公开 YAML 只放 `${DASHSCOPE_API_KEY}` 占位符。不要将实际密钥写入 SKILL、论文或提交包。

## 实际调用关系

| 步骤 | 接口 / 模型 | 程序与记录 |
| --- | --- | --- |
| 文献元数据 | GET `https://export.arxiv.org/api/query`，无需 Key | `literature_search.py`，Atom 缓存及 `.provenance.json` |
| 规划、初稿、审阅、修订 | POST `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，`qwen3.8-max` | `write_paper.py` → `paper_content/editorial.py` → `model.py`；阶段 JSON、usage、耗时 |
| Methodology 配图 | POST `https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation`，`qwen-image-3.0-pro` | `generate_methodology.py`；`X-DashScope-Async: enable` |
| 查询图像任务 | GET `https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}` | 每五秒查询同一任务；成功后立即下载临时图片 URL |
| 实测数据、图表、排版 | 本地 Python / Matplotlib / LaTeX | 不调用图像模型绘制实验数值 |

截至本次核对，Qwen3.8-Max 为千问旗舰文本模型；千问图像 3.0 Pro 擅长文本与复杂布局，适合方法示意图。配置保留同地域的 `DASHSCOPE_BASE_URL`、`DASHSCOPE_IMAGE_BASE_URL` 覆盖入口，便于迁移到百炼业务空间专属域名。旧的 dashscope 域名当前仍受支持。依据：[千问旗舰公告](https://www.alibabacloud.com/zh/press-room/alibaba-unveils-qwen3-8-max?_p_lc=1)、[文本接口](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions)、[图像 API](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference)。

`client_provider: OpenAI` 表示文本客户端采用兼容协议，服务地址仍为阿里云；它不表示需要 OpenAI 账号或 Key。图像端使用百炼原生异步协议，两者不要混用路径。

## arXiv 如何配置与使用

```yaml
arxiv:
  api_url: https://export.arxiv.org/api/query
  user_agent: CCF-BDCI-PaperResearch/2.0 (research metadata client)
  interval_seconds: 3.1
  timeout_seconds: 60
```

API 没有密钥参数。客户端使用 HTTPS、串行连接、至少三秒间隔、有限重试，并缓存原始 Atom XML。按关键词搜索：

```powershell
python jiuwenswarm/research-paper-generator/scripts/literature_search.py --query 'all:agent AND all:memory' --max-results 20 --config jiuwenswarm/research-paper-generator/examples/dashscope-research.yaml --output output/literature-search.json
```

重查当前六篇参考文献：

```powershell
python jiuwenswarm/research-paper-generator/scripts/literature_search.py --ids 2310.08560,2410.10813,2304.03442,2307.03172,2305.10250,2502.12110 --config jiuwenswarm/research-paper-generator/examples/dashscope-research.yaml --output output/literature-verified.json
```

现有研究 brief 使用 `memgpt`、`longmemeval` 等显式别名；不要用原始 ID 输出直接覆盖别名版 literature，否则必须同步更新 brief 中的引用。检索元数据不等于阅读论文，也不证明任何研究结论。规则依据：[arXiv API 手册](https://info.arxiv.org/help/api/user-manual.html)、[使用条款](https://info.arxiv.org/help/api/tou.html)。

## 生成方法图

```powershell
python jiuwenswarm/research-paper-generator/scripts/generate_methodology.py --output output/methodology-new.png
```

提示词保存在 `prompts/methodology.txt`，明确两条真实路径：文件前缀截断，以及经过模型写入、词法排序和整项打包的 L1 记忆。配图不包含未测试的 L2/L3、Embedding 或团队同步。输出 PNG 和同名 `.provenance.json`，记录模型、任务 ID、请求参数、usage、提示词与图片哈希；不保存密钥或临时签名 URL。

若网络中断且已取得 task ID，可恢复同一任务：

```powershell
python jiuwenswarm/research-paper-generator/scripts/generate_methodology.py --resume-task <任务ID> --output output/methodology-recovered.png
```

接口任务查询有效期为 24 小时；图片 URL 也有有效期，应及时下载。创建任务不自动重试；额度不足或模型无权限时会退出并保留报告，避免重复计费和假成功。

## 在线论文与离线重排

先检查配图，再指定它生成论文：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --methodology-image output/methodology-new.png --output output/research-new --compile
```

也可用 `--generate-methodology` 在写作前调用图像接口；默认不带此参数时使用仓库已保存并检查过的配图。研究模式保存 `editorial_plan.json`、`editorial_draft.json`、`editorial_review.json`、`editorial_revision.json`。为避免非流式请求的长思考过程触发网关超时，各阶段保留旗舰模型，但关闭 thinking，规划/审阅最多 6000 输出 Token，正文最多 16000；请求设置和消耗进入报告。最多一次正文格式修复。

恢复中断的阶段，必须保持输入一致，并选一个新输出目录：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --resume-from output/research-new/paper --output output/research-resumed --compile
```

仅重排已有正文，不再付费：

从已提交的研究说明、文献、实验和保存正文开始，一条命令离线联调第 3 / 4 / 5 部分：

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --content-json jiuwenswarm/research-paper-generator/examples/memory-research.content.json --output output/research-offline --compile
```

此模式不读取模型配置、不加载凭据，也不调用图像 API；不要搭配在线生成或恢复参数。已有框架可继续使用以下命令：

```powershell
python jiuwenswarm/research-paper-generator/scripts/fill_content.py output/research-new/framework --content-json output/research-new/paper/content.json --methodology-image output/methodology-new.png --output output/research-typeset --compile
```

新框架自带 `evidence/raw/` 快照。交接时复制整个框架目录，不能只复制 `outline.json` 或 `sections/`；内容填充与质量检查按 `project_path` 解析证据，且仍然校验哈希。已填充论文的 `evidence/` 同样支持整个工程迁移。

论文写作调用与实验调用分开记账。本次研究依据仍是两份已保存的 qwen-plus 实验；重新写论文不等于重跑实验。质量检查通过也不代表取得比赛评审 Token、论文达到样例的实验规模，或已获人工学术认可。

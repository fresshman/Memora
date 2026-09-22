<div align="center">

<h1>🧠 Memora</h1>

<p><strong>端侧离线 · 隐私优先的对话智能复盘工具</strong></p>

<p>
<img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white">
<img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&amp;logoColor=white">
<img alt="Model" src="https://img.shields.io/badge/Model-Spark%20X2.5%204B%2F1.7B-FF6B35">
<img alt="Offline" src="https://img.shields.io/badge/Runs_100%25-Offline_%26_On__device-2ea44f">
<img alt="No torch/GPU" src="https://img.shields.io/badge/No-torch_%2F_GPU-999999">
<img alt="Tests" src="https://img.shields.io/badge/Tests-125%20passed-brightgreen">
</p>

<p>Spark-X2.5 端侧模型 ・ llama.cpp ・ 本地 bge-m3 + FAISS ・ FastAPI + Next.js</p>

<p>
<a href="README.en.md">English</a>
&nbsp;|&nbsp;
<strong>简体中文</strong>
</p>

</div>

---

> 一个**完全离线、隐私优先**的对话智能复盘工具：把 **Spark-X2.5 端侧小模型 + 本地检索增强（RAG）**
> 装进一台 **8GB 内存的普通 Windows PC**，**数据从不出本机**，即可把成百上千条工作群聊，
> 一键凝练成**核心结论 / 待办事项 / 风险提示**结构化纪要，并支持基于全部对话的追问与溯源。
>
> **无需 GPU、无需 torch、无需联网** —— 一个本地文件夹，替掉「要把聊天记录上传到云端的纪要 SaaS」。

---

## ✨ 为什么是 Memora

云端会议纪要工具越来越强，但工业场景里，工作群聊往往包含**客户信息、上线窗口、故障细节、责任人**——
这些内容不适合上传第三方；而端侧 1.7B/4B 小模型又受困于**上下文长度、长文档遗忘、结构化不稳定**。
Memora 用一套全本地的工程链路，把「小模型能不能干好严肃的长对话复盘」这件事做成可量化、可复现：

- 🔒 **真离线、真隐私**：默认 `MEMORA_ENFORCE_OFFLINE=1`，模型缺失也**绝不联网**；推理只绑定 `127.0.0.1`。
  手机 / 身份证 / 银行卡 / 邮箱 / 车牌 / 护照 / 人名在送入模型**之前**就本地占位脱敏，映射只存内存、报告后一键还原；落库记录用 Fernet 加密。
- 📚 **超长对话不丢信息（本地 RAG）**：短对话**全量直喂、零损耗**；超长对话切分为块，用本机 **bge-m3 embedding + FAISS**
  做「多路语义召回 + 时间线骨架」，并设**硬上下文预算**保证永不撑爆模型窗口——而不是简单砍掉最旧的消息。纯 CPU、无 torch。
- 🧾 **结构化复盘 + 可溯源问答**：输出固定四段（核心结论 / 待办 / 风险 / 关键信息），并把散落在纪要里的
  **会议时间、地点、安排确定性归位**到结论段；问答基于全部对话检索，回答附**原文引用**，未提及即明说「未讨论」。
- 💬 **真实多平台解析**：微信（txt，含 GBK）、钉钉（csv）、飞书（html）导出记录自动嗅探编码与格式，附 10 份真实解析样本库。
- ⚡ **产品级体验**：SSE **逐 token 流式**输出、Next.js 单页应用、单端口同源部署（最终用户**无需 Node.js**）、Markdown/PDF 导出、批量复盘。
- 🧩 **模型一键管理**：首页与模型页显式推荐 **Spark-X2.5-4B / 1.7B**，自动检测本地是否已安装，缺失时弹窗确认后经
  **ModelScope `snapshot_download` 自动下载**官方 Q4_K_M GGUF，下载即用、无需手工转换。

## 📊 评测与消融（数据说话）

内置 50 例合成对话评测集（30 短 + 20 超长，含 346 条探针式问答），贪心解码（`MEMORA_TEMP=0`）结果可复现，
指标覆盖**待办 / 风险 / 决定的召回与精确率、风险全文完整度、问答证据命中率、幻觉率**，一键生成单文件 HTML 报告。

**主榜（Spark-X2.5-4B，Q4_K_M）**

| 场景 | 待办召回 | 风险召回 | 决定召回 | 风险完整度 | QA 证据命中 | 幻觉率 |
|---|---|---|---|---|---|---|
| 短对话 · 全量直喂（n=30） | 0.928 | 0.967 | **0.900** | 0.983 | 1.000 | **0** |
| 超长对话 · 本地 RAG（n=20） | 0.900 | 0.942 | **0.908** | 0.958 | 1.000 | **0** |

**超长上下文策略消融（n=6/组）**

| 策略 | 待办 / 风险召回 | QA 证据命中 | 结论 |
|---|---|---|---|
| 4B 全量直喂（超出上下文窗口） | 0.250 / 0.250 | 0.000 | 崩溃、约 639s，不可用 |
| 4B 规则时间线压缩 | 0.944 / 0.917 | 1.000 | 无 embedding 时的降级方案 |
| **4B 本地 RAG（bge-m3 + FAISS）** | **0.900 / 0.942** | **1.000** | **召回与可用性兼得，默认方案** |
| 1.7B 本地 RAG（极低资源兜底） | 0.694 / 0.611 | 0.333 | 4GB 内存可跑，问答能力弱 |

> 结论：本地 RAG 把超长对话从「全量直喂崩溃（召回 0.25、问答 0）」拉回到 **0.90+ 召回、问答证据命中 1.0、零幻觉**。
> 完整结果见 `evals/results/final/report.html`。

## 🖥️ 功能页面

| 页面 | 路径 | 说明 |
|---|---|---|
| 对话复盘（首页） | `/` | 粘贴 / 上传聊天记录 → PII 预览 → 流式生成结构化报告，一键导出 |
| 智能问答 | `/qa/` | 基于全部对话追问，回答带原文引用 |
| 模型管理 | `/models/` | 双模型推荐、本地状态检测、ModelScope 一键下载、在线切换 |
| 批量复盘 | `/batch/` | 多份记录批量处理与汇总 |
| 语音纪要（可选） | `/voice/` | 接入本地 whisper.cpp 转写后复盘 |
| 历史记录 | `/history/` | 本地加密存储的复盘历史 |

## 🚀 快速开始

**环境要求**：Windows 10/11（64 位）、Python 3.10–3.12（推荐 3.12）；4B 模型建议 8GB 内存、1.7B 约 4GB；磁盘约 3GB。
仅当需要**修改前端**时才需要 Node.js 18+，纯使用无需安装。

```bash
# 1) 获取代码并安装依赖（默认链路无 torch、无需编译）
git clone https://gitee.com/FreeBlank/memora.git
cd Memora
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# 2) 环境自检：依赖 / 推理引擎 / 模型 / 磁盘逐项检查并给出修复建议
python scripts/doctor.py

# 3) 一键启动（自动自检 → 起后端；有静态前端时单端口直达）
scripts\start.bat
#   随后浏览器访问 http://127.0.0.1:8000
```

**准备推理引擎（llama.cpp）**：下载 [llama.cpp 官方每日构建](https://github.com/ggml-org/llama.cpp/releases)
中 **2026-09-07 之后、含 Spark2_5 架构**的 Windows CPU 版（如 `llama-b11046-bin-win-cpu-x64.zip`），
解压到 `tools/llamacpp/bin/`；或设置环境变量 `MEMORA_LLAMASERVER_PATH` 指向 `llama-server.exe`。

**准备模型（安装阶段需要网络）**：二选一——

- 界面：启动后进入「模型管理」，在推荐卡片上点「下载此模型」→ 弹窗确认，系统自动经 ModelScope 拉取官方 Q4_K_M GGUF；
- 命令行（安装阶段先 `set MEMORA_ENFORCE_OFFLINE=0`）：

```bash
python scripts/prepare_model.py                                  # 默认 4B
python scripts/prepare_model.py --model XHToken/Spark-X2.5-1.7B  # 轻量 1.7B
```

对应的官方 ModelScope 命令（只拉取 Q4_K_M 单文件）：

```python
from modelscope import snapshot_download
snapshot_download('XHToken/Spark-X2.5-4B-GGUF',   allow_file_pattern=['*Q4_K_M*'])  # ≈2.5GB，8GB+ 内存
snapshot_download('XHToken/Spark-X2.5-1.7B-GGUF', allow_file_pattern=['*Q4_K_M*'])  # ≈1.1GB，4GB+ 内存
snapshot_download('gpustack/bge-m3-GGUF',         allow_file_pattern=['*Q4_K_M*'])  # 本地 RAG 向量模型，≈438MB
```

> **离线红线**：默认 `MEMORA_ENFORCE_OFFLINE=1`，应用绝不联网，模型缺失只报错并给出命令。
> 断网演示时保持默认即可；也可在联网机下载后，把 `root/models/models/XHToken--Spark-X2.5-*-GGUF` 整个目录拷到目标机同位置。

## 📦 完全离线部署（交付到断网机器）

在一台**有网络**的同架构打包机（64 位 Windows + Python 3.10–3.12）上执行一次：

```powershell
# 构建应用 + 静态前端 + 本地 wheelhouse（约 70 余个 wheel，含 faiss/numpy 等二进制包）
powershell -ExecutionPolicy Bypass -File scripts/build_offline.ps1
# 若要连模型一起打入（约 4GB），加 -IncludeModels
```

产物为 `release/Memora/`，整体拷贝到**完全断网**的 Windows 机器后：

```bat
install_offline.bat   :: 从本地 wheelhouse 纯离线安装依赖（pip --no-index）
start.bat             :: 启动，浏览器访问 http://127.0.0.1:8000
```

**断网验收清单**：`python scripts/doctor.py` 全绿 → 物理断网 → 完成一次超长对话复盘与追问。
仓库内置 `scripts/e2e_offline_check.py`（24 项端到端检查：静态托管、PII 脱敏与还原、SSE 流式、短/超长上下文自动切换、推理期零外联）。

## 🏗️ 系统架构

后端是薄层 FastAPI，业务逻辑全部内聚在 `memora/`；默认后端在首次推理时于本机随机端口拉起
`llama-server`（仅绑定 127.0.0.1），通过 OpenAI 兼容协议通信，退出 / 切换模型时终止子进程。

```text
聊天记录(txt/csv/html)
        │  编码嗅探 · 多平台解析（微信/钉钉/飞书）
        ▼
   PII 本地脱敏（映射仅存内存，可一键还原）
        │
        ├── 短对话 ──► 全量直喂（零损耗）
        └── 超长对话 ─► bge-m3 embedding + FAISS 多路召回 + 时间线骨架（硬上下文预算）
        ▼
  llama-server · Spark-X2.5 GGUF（OpenAI 兼容，纯 CPU / 可选 GPU）
        ▼
 结构化报告（结论/待办/风险/关键信息 + 会议决定归位）── SSE 逐 token ──► Next.js 前端
        │                                              问答：同一检索上下文 + 原文引用
        ▼
 Fernet 加密落库（data/vault） · Markdown / PDF 导出
```

**目录结构**

```text
Memora/
├── memora/                 # 核心业务逻辑（被 FastAPI 复用）
│   ├── parsers/            #   微信 / 钉钉 / 飞书解析 + 编码嗅探
│   ├── pii/                #   PII 脱敏与还原
│   ├── retrieval/          #   bge-m3 + FAISS 本地 RAG、上下文预算与时间线骨架
│   ├── agent/              #   LangChain 复盘 / 问答 / 语音三链、流式
│   ├── report/             #   报告结构化与「会议决定归位」（评测与产品同一口径）
│   ├── prompts/            #   提示词模板
│   ├── backend/            #   llama-server 子进程后端 + 可选 SGLang 后端
│   ├── storage/            #   Fernet 本地加密
│   ├── whisper/            #   本地语音转写（可选）
│   ├── model_fetch.py      #   模型获取状态机（官方 GGUF 下载 + safetensors 转换兜底）
│   ├── exporter.py         #   Markdown / PDF 导出
│   └── batch.py            #   批量复盘
├── server/                 # FastAPI：单端口 8000，web/out 同源托管
│   └── routes/             #   review / qa / models / records / export / voice / health
├── web/                    # Next.js + React + Tailwind（app 页面 + out 静态产物）
├── evals/                  # 评测集、指标、worker/runner、单文件 HTML 报告
├── samples/                # 微信/钉钉/飞书真实解析样本库
├── scripts/                # doctor / prepare_model / start.bat / build_offline.ps1 / e2e
├── tests/                  # 125 项 pytest（不加载模型、不联网）
├── tools/llamacpp/bin/     # llama.cpp 官方二进制（自行下载放置，不入库）
├── requirements.txt        # 完整依赖（开发 / 打包）
└── requirements-runtime.txt# 运行时依赖（离线安装用）
```

## ⚙️ 主要配置（`.env` / 环境变量）

复制 `.env.example` 为 `.env` 按需修改；所有项均可被同名环境变量覆盖。

| 键 | 默认值 | 说明 |
|---|---|---|
| `MEMORA_MODELS_ROOT` | `../root/models` | 模型根目录（ModelScope 缓存） |
| `MEMORA_MODEL_ID` | 4B | 当前模型（一般由模型管理页写入 `data/settings.json`） |
| `MEMORA_BACKEND` | `llamacpp` | `llamacpp`（本机子进程）/ `sglang`（外部 GPU server） |
| `MEMORA_ENFORCE_OFFLINE` | `1` | 离线红线：1 = 禁止一切下载，模型缺失只报错 |
| `MEMORA_N_CTX` / `MEMORA_KV_QUANT` | `32768` / `q8_0` | 上下文窗口 / KV 量化（8GB 友好，约占 3.5GB） |
| `MEMORA_N_GPU` | `0` | GPU 卸载层数，0 = 全 CPU，-1 = 全部上 GPU |
| `MEMORA_RAG_ENABLE` | `1` | 超长对话本地 RAG 开关；无 embedding 时自动降级为规则压缩 |
| `MEMORA_PII_REDACT` | `1` | PII 脱敏开关（含人名角色化） |
| `MEMORA_TEMP` / `MEMORA_MAX_REVIEW` / `MEMORA_MAX_QA` | `0.3` / `4096` / `1024` | 解码温度与最大生成长度 |

## 🧪 测试与评测复现

```bash
python -m pytest tests/ -q                          # 125 项单测：不加载模型、不联网
# 真机离线端到端（需已放置模型，24 项）
set MEMORA_ENFORCE_OFFLINE=1 && python scripts/e2e_offline_check.py
# 全量评测与消融（需模型，耗时较长，贪心解码可复现，断点续跑）
cd evals && python runner.py
```

## 🗺️ 路线图

- [x] 多平台解析、PII 脱敏、本地 RAG、SSE 流式、模型一键下载、离线发布包、评测与消融
- [ ] whisper.cpp / ffmpeg 语音链路随包分发（当前为可选实验）
- [ ] PyInstaller / WebView 桌面 EXE 一键安装包
- [ ] 更多 IM / 会议平台导出格式解析
- [ ] 8GB / 16GB、Intel / AMD、有无独显的配置矩阵实测

## 🙏 致谢

Memora 站在开源社区的肩膀上：[Spark-X2.5](https://modelscope.cn/models/XHToken/Spark-X2.5-4B-GGUF) 端侧模型、
[llama.cpp](https://github.com/ggml-org/llama.cpp)、[bge-m3](https://modelscope.cn/models/gpustack/bge-m3-GGUF)、
ModelScope、LangChain、FastAPI、Next.js。各模型与第三方组件遵循其各自许可证。

## 📄 许可证

本仓库当前**尚未声明开源许可证**（默认保留所有权利），仅用于学习与竞赛展示。
如需开源，建议补充 `LICENSE`（如 MIT）并再次确认所分发模型 / 二进制的许可条款。

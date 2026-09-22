# Memora · 端侧离线私密对话智能复盘工具

> 基于 **Spark-X2.5 端侧模型（4B / 1.7B，Q4_K_M 量化 GGUF）** 的离线私密对话复盘与智能纪要工具。
> 全部推理在本机完成，**零数据上传**；默认通过本机 llama-server 子进程推理，**免编译、免 torch**，
> 4B 量化后约 2.5GB，8GB 内存 PC 即可运行。

---

## 一、关键架构决策

| 层 | 选择 | 理由 |
|----|------|------|
| 智能体编排 | **LangChain** | 提示词模板、流水线编排、结构化输出，与后端解耦 |
| 默认推理引擎 | **llama.cpp 官方 llama-server 子进程** | 免 Python 编译绑定；官方每日构建已含 Spark2_5；OpenAI 兼容接口；可整体离线分发 |
| 可选推理引擎 | **SGLang（外部 server 模式）** | GPU 高性能分支：用户自起 server，连 OpenAI 兼容端点 |
| 模型获取 | **ModelScope 官方 Q4_K_M GGUF，下载即用** | 单文件（4B≈2.5GB / 1.7B≈1.1GB），无需 safetensors→GGUF 转换 |
| 后端 | **FastAPI + uvicorn** | 薄层 HTTP 适配，复用 `memora/` 全部业务逻辑 |
| 前端 | **Next.js + React + Tailwind** | 产品级 UI，工业简洁风；模型管理页显式推荐双端侧模型 |

**模型来源（默认平台 ModelScope，官方命令）：**

```python
from modelscope import snapshot_download
snapshot_download('XHToken/Spark-X2.5-4B-GGUF',   allow_file_pattern=['*Q4_K_M*'])  # ≈2.5GB
snapshot_download('XHToken/Spark-X2.5-1.7B-GGUF', allow_file_pattern=['*Q4_K_M*'])  # ≈1.1GB
```

> 历史坑：Spark2_5 架构 2026-09-06 才合入 llama.cpp，PyPI 上的 llama-cpp-python
> 发布版内置 llama.cpp 可能滞后（加载报 `unknown model architecture: 'spark2_5'`）。
> 因此默认后端不依赖 Python 绑定，直接使用 llama.cpp 官方每日构建的 llama-server。

---

## 二、目录结构

```
Memora/
├── .env.example              # 配置模板（复制为 .env 使用）
├── requirements.txt          # 依赖清单（默认链路无 torch、无 llama-cpp-python）
├── README.md
├── start.bat（在 scripts/）   # Windows 一键启动后端+前端
├── tools/
│   └── llamacpp/bin/         # 随包 llama.cpp 官方二进制（llama-server 等，免编译）
├── memora/                   # 核心业务逻辑（被 FastAPI 后端复用）
│   ├── config.py             # 集中配置（.env 加载、路径/后端/参数、模型缓存布局解析）
│   ├── log.py                # 中文日志（控制台 + 文件）
│   ├── exporter.py           # 报告导出（Markdown 零依赖 + PDF 工业简洁风）
│   ├── batch.py              # 批量复盘
│   ├── model_fetch.py        # 模型获取状态机（官方 GGUF 下载 + safetensors 转换兜底）
│   ├── backend/
│   │   ├── base.py           # 后端抽象 + Spark 官方对话模板 + 思考链清洗
│   │   ├── llamacpp_backend.py  # 默认：拉起/管理本机 llama-server 子进程
│   │   └── sglang_backend.py    # 可选：连接外部 OpenAI 兼容 server
│   ├── parsers/              # 微信/钉钉/飞书 解析，自动嗅探
│   ├── prompts/              # 提示词模板
│   ├── agent/                # LangChain 复盘智能体（复盘/问答/语音纪要三链）
│   ├── whisper/              # 本地 Whisper.cpp 转写封装（可选）
│   └── storage/              # Fernet 本地加密存储
├── server/                   # FastAPI 后端
│   ├── main.py / deps.py / session.py / schemas.py
│   └── routes/               # health/review/qa/voice/records/export/models
├── web/                      # Next.js 前端
│   ├── app/                  # 页面：复盘(首页)/模型管理/批量/问答/语音/历史
│   ├── components/           # Sidebar、ReportCard、StatusBadge、EmptyState
│   └── lib/api.ts            # API 客户端
├── scripts/
│   ├── prepare_model.py      # 命令行备模（默认拉官方 Q4 GGUF；--from-safetensors 走转换）
│   ├── doctor.py             # 环境自检（依赖/引擎/模型/磁盘/可选项）
│   └── start.bat             # Windows 一键启动
├── tests/                    # pytest 单元测试（47 用例，不加载模型、不联网）
└── data/                     # 运行时生成（settings.json、vault 加密记录、logs、exports）
```

---

## 三、安装与准备

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

默认链路**不需要** torch、不需要编译 llama.cpp。

### 2. 准备 llama-server 推理引擎（三选一）

- **方式一（推荐，离线包已内置）**：把 llama.cpp 官方每日构建 zip
  （如 `llama-b11046-bin-win-cpu-x64.zip`，需 2026-09-07 之后、含 Spark2_5）
  解压到 `Memora/tools/llamacpp/bin/`（仓库随包已放好一份）。
- **方式二**：设置环境变量 `MEMORA_LLAMASERVER_PATH` 指向 llama-server 可执行文件。
- **方式三**：在项目同级放 `../llama.cpp/build/bin/llama-server`（自行编译最新 master）。

### 3. 下载模型（两种方式）

- **界面方式**：启动应用 → 左侧「模型管理」→ 在推荐卡片上点「下载此模型」→
  弹窗确认「是，开始下载」，系统经 ModelScope 自动下载官方 Q4_K_M GGUF，
  完成后状态变「已就绪」，点「使用此模型」即可切换。
- **命令行方式**：

```bash
# 默认 4B；安装阶段如需联网下载，先设置 MEMORA_ENFORCE_OFFLINE=0
python scripts/prepare_model.py
python scripts/prepare_model.py --model XHToken/Spark-X2.5-1.7B
```

> 离线红线：默认 `MEMORA_ENFORCE_OFFLINE=1`，应用绝不联网。
> 安装阶段设 `MEMORA_ENFORCE_OFFLINE=0` 下载模型；比赛演示时保持默认即可断网运行。
> 离线机器也可在联网机下载后，把 `root/models/models/XHToken--Spark-X2.5-xB-GGUF`
> 整个目录拷贝到目标机器同位置。

**兜底（仅当你拿到的是 safetensors 原始仓库）**：备好含 Spark2_5 的 llama.cpp 后

```bash
python scripts/prepare_model.py --from-safetensors --llamacpp ../llama.cpp
```

### 4. 自检与启动

```bash
python scripts/doctor.py          # 检查依赖/引擎/模型/磁盘，给出修复建议
# Windows 一键启动（后端 8000 + 前端 3000）
scripts\start.bat
```

或手动启动：

```bash
# 终端 1
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
# 终端 2
cd web && npm install && npm run dev
# 浏览器打开 http://localhost:3000
```

首次推理时后端会自动在随机本机端口拉起 llama-server 并加载当前模型，
切换模型时自动关闭旧进程；日志见 `data/logs/llama-server.log`。

---

## 四、模型管理页交互（用户需求闭环）

1. 首页与「模型管理」页**显式推荐 Spark-X2.5-4B / Spark-X2.5-1.7B**；
   首页在当前模型未就绪时显示黄色引导横幅，一键跳转模型管理页。
2. 每张模型卡片实时显示本地状态：`已就绪（GGUF，可直接使用）/ 仅有 safetensors / 本地未安装`。
3. 未安装时点「下载此模型」→ 弹窗「本地未检测到 XX，是否从 ModelScope 下载到本地？」
   → 点「是，开始下载」自动下载官方 Q4_K_M GGUF（仅单文件），页面 2.5s 轮询进度。
4. 离线模式下下载请求返回 409，并给出可在联网机执行的官方命令。
5. 下载完成点「使用此模型」即持久化选择（`data/settings.json`）并重建推理链。

后端接口：`GET /api/models/config`、`GET /api/models`、
`POST /api/models/download|convert|select`、`GET /api/models/status`。

---

## 五、可选：SGLang server 模式（GPU）

```bash
pip install sglang
python -m sglang.launch_server --model-path XHToken/Spark-X2.5-4B \
    --host 127.0.0.1 --port 30000 --context-length 1000000
```

设置 `MEMORA_BACKEND=sglang`（及 `MEMORA_SGLANG_URL` / `MEMORA_SGLANG_MODEL`）后启动后端。

---

## 六、语音模块（可选）

需自行编译 whisper.cpp，二进制放到 `whisper.cpp/build/bin/whisper-cli.exe`；
首次使用自动下载 `ggml-base.bin`（仅安装阶段用网）；非 wav 音频需系统装有 ffmpeg。

---

## 七、主要配置项（.env / 环境变量）

| 键 | 默认值 | 说明 |
|----|--------|------|
| `MEMORA_MODELS_ROOT` | `../root/models` | 模型根目录（ModelScope 缓存） |
| `MEMORA_MODEL_ID` | 4B | 当前模型（一般由模型管理页写入 settings.json） |
| `MEMORA_BACKEND` | `llamacpp` | `llamacpp`（本机 server）/ `sglang`（外部 server） |
| `MEMORA_LLAMASERVER_PATH` | 空 | 显式指定 llama-server 路径 |
| `MEMORA_LLAMASERVER_PORT` | `0` | server 端口，0=自动选空闲端口 |
| `MEMORA_N_CTX` | `32768` | 上下文窗口（8GB 机器建议 ≤32768） |
| `MEMORA_N_GPU` | `0` | 上 GPU 的层数，0=全 CPU，-1=全部上 GPU |
| `MEMORA_THREADS` | `0` | CPU 线程数，0=自动 |
| `MEMORA_KV_QUANT` | `q8_0` | KV cache 量化（q8_0/q4_0/f16） |
| `MEMORA_TEMP` | `0.3` | 温度 |
| `MEMORA_MAX_REVIEW` / `MEMORA_MAX_QA` | `4096` / `1024` | 复盘 / 问答最大生成长度 |
| `MEMORA_ENFORCE_OFFLINE` | `1` | 离线红线：1=禁止一切下载 |
| `MEMORA_SGLANG_URL` / `MEMORA_SGLANG_KEY` / `MEMORA_SGLANG_MODEL` | `http://127.0.0.1:30000/v1` / `EMPTY` / 空 | 外部 server 配置 |

---

## 八、比赛演示流程

1. `python scripts/doctor.py` 确认全绿；断开网络证明纯离线。
2. 导入一份工作群聊天记录（txt/csv/html），首页一键复盘 → 结构化报告（结论/待办/风险）。
3. 自然语言提问，基于全部对话问答。
4. 模型管理页展示双端侧模型与本地状态，现场切换 4B/1.7B 对比速度。
5. 【加分】导入会议录音，本地转写并生成纪要。
6. 数据全部在本机 `data/`，加密存储，一键清空可彻底删除。

---

## 九、单元测试

```bash
python -m pytest tests/ -q
```

覆盖解析器（微信/钉钉/飞书/嗅探/兜底）、配置与模型缓存布局、加密存储、智能体报告切片、
导出、批量汇总、模型获取状态机（官方 GGUF 仓库布局/优先级/离线红线）、Spark 模板与思考链清洗、
llama-server 发现与启动参数构造，共 47 个用例，不依赖模型加载、不联网。

---

## 十、架构说明与消融支持

后端是薄层，只做 HTTP 适配；业务逻辑（解析、推理、加密、导出）都在 `memora/`。
默认后端在首次推理时于本机随机端口拉起 llama-server（仅绑定 127.0.0.1），
通过 OpenAI 兼容协议通信，退出/切换模型时终止子进程。
未来打包桌面应用时，FastAPI 与 llama-server 作为子进程随 EXE 分发，
Next.js 静态导出后由 webview 或 FastAPI StaticFiles 托管。

**消融实验**：对照组①全量上下文直接分析；对照组②调小 `MEMORA_N_CTX` + 长文本分片模拟 RAG。
评价指标（待办准确率/关键信息召回/风险完整度）可在 `memora/agent` 外层评估脚本接入。

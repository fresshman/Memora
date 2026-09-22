# Memora 差距评估与离线部署整改清单

> 评审时间：2026-09-19。评审方式：全量源码走读 + 本机实测（pytest、依赖导入、模型发现、磁盘产物核查、公开资料核验）。
> 结论一句话：**架构骨架和工程审美在线，但"端到端推理"在当前机器上从未真正跑通过，离线分发形态基本为零；竞赛硬核材料（评测/消融/性能数据）尚空白。** 修通 P0 约需 2 天，补齐一等奖竞争力约需 2 周。

---

## ★ 实施进度总览（2026-09-21：P1 五模块已落地）

按 M0→M5 顺序整改，当前状态：

| 里程碑 | 内容 | 状态 | 验收证据 |
|---|---|---|---|
| M0 | 多平台解析样本库 + parser 加固 | 完成 | 微信/钉钉/飞书 9 个真实样本 + manifest；编码探测；解析回归测试 |
| M1 | RAG 超长对话（本地 bge-m3 + faiss） | 完成 | 20 个超长例纯检索召回待办/风险/决定均 100%；上下文由 1.6 万字收敛到约 7600 字/20 块 |
| M2 | 评测集 + 消融（准确率/召回/风险完整度） | 完成 | 50 合成例（30 短+20 超长、346 条探针 QA）、metrics/worker/runner/单文件 HTML 报告；贪心解码可复现；定稿主榜 QA 证据命中 1.0、幻觉率 0，决定段内召回 短 0.90 / 超长 0.91（含确定性决定归位） |
| M3 | 流式输出 SSE | 完成 | `/api/review/stream`、`/api/qa/stream`；前端逐字输出 + 上下文模式徽标；6 项测试通过、tsc 0 错误；**真机终验复盘 186 个 delta、问答 53 个 delta 逐块到达** |
| M4 | PII 本地脱敏 | 完成 | 手机/身份证(校验位)/银行卡(Luhn)/邮箱/IPv4/车牌/护照 + 人名角色化；解析后、入模型与索引前脱敏，映射仅存内存、可逆；前端提示与一键还原；10 项测试通过 |
| M5 | 离线包断网复测 | 打包/安装链路完成；**真机单端口 24/24 通过、推理期零外联** | Next 静态导出 + FastAPI 单端口同源托管；`build_offline.ps1` / `install_offline.bat`；干净 Python 3.12 venv 用 `--no-index` 安装成功；真机静态托管/PII/SSE/RAG 共 24 项端到端全过 |

- 测试规模演进：M0 72 → M1 83 → M2 93 → M3/M4/M5 后 114 → RAG 硬预算回归 115 → 会议决定归位 **125**，全部通过；干净 Python 3.12 venv 发布树同样 **125 passed**。
- 全量主榜 + 消融评测（68 格）：v1 冻结输出 `evals/results/baseline_v1/`；**最终定稿口径（v1 模型 + 确定性决定归位）报告 `evals/results/final/report.html`**；prompt v2 实验留存 `evals/results/prompt_v2/`（全量 A/B 证伪，未采用）。
- 离线分发操作见《Memora_离线部署指南.md》：单端口 `http://127.0.0.1:8000`，最终用户机器无需 Node.js。

> **真机端到端终验（2026-09-21，`scripts/e2e_offline_check.py`，24 项全过）** 还抓到并修复了两处单测/干净环境无法暴露的真实缺陷：
> 1. 流式"假流"：ChatOpenAI 构造参数 `streaming=False` 导致 `.stream()` 一次性返回（delta 只有 1 块）；改为 `streaming=True` 后复盘 186 块、问答 53 块逐 token 到达（`.invoke()` 行为不变）。
> 2. RAG 上下文缺硬红线：强信号块设计上豁免单面字符预算，真实长对话正常（约 7600 字），但信号词异常密集时会无限膨胀、撑爆 32768 上下文直接 400；已加"绝不超过 MAX_INPUT_CHARS"的全局硬预算（强信号也受限）+ 头尾锚点预留，并补回归测试。正常对话远低于红线、行为不变。
>
> **决定归位迭代结论（评测驱动，2026-09-21）**：
> 1. 先试 prompt v2（让模型把敲定的时间/金额/安排写回结论段），全量 50 格 A/B **证伪**——短对话决定段内召回虽 0.783→0.850，但风险全文完整度 0.983→0.917、超长决定召回 0.883→0.775，属“按下葫芦浮起瓢”，**已回退 v1**（实验结果留存 `evals/results/prompt_v2/`）。
> 2. 根因数据：v1 共 98 个 gold 决定点，段内漏 15 个中 13 个全文已命中——9 个被埋在“关键信息提取”段（多为会议时间/地点分行罗列）、3 个落在待办段。遂改用**确定性后处理**：新增 `memora/report/sections.py`，把关键信息段中“事件名 + 就近时间 + 会场地点”齐备的安排聚合成一句决定补回结论段（只复制不移动，设取消/改期安全闸、事件去重、会场白名单、时间就近配对）。离线重放 50 格：**决定段内召回 短对话 0.783→0.900、超长 0.883→0.908，精确率与待办/风险/QA 全部零变化**，10 项单测覆盖；评测切段与产品结构化共用同一模块（评测口径 == 产品口径）。
> 3. 离线发布包已用最终代码重新构建；干净 Python 3.12 venv `--no-index` 安装、发布树 **125 项测试全过**。
>
> 仍待办（可选）：① 真机物理拔网线终验（当前为 ENFORCE_OFFLINE + netstat 采样推理期零外联）；② 4B 目录 7.8GB safetensors 原始权重**用户已确认保留**；③ whisper.cpp / ffmpeg 语音链路（可选增强）。

---

## 0. 实测证据（不是推测）

| 检查项 | 实测结果 |
|---|---|
| pytest | 21 passed（但全部不加载模型，无法证明推理链路可用） |
| `llama_cpp` 依赖 | **未安装**（ModuleNotFoundError），默认后端无法 import |
| `langchain_community` 依赖 | **未安装**；`llamacpp_backend.py` 第 43 行 `from langchain_community.llms import LlamaCpp` 必挂 |
| `bs4`（beautifulsoup4） | **未安装**，飞书 HTML 解析静默退化为正则 |
| `modelscope` | 已装 1.39.1，但 **requirements.txt 未声明** |
| langchain 实际版本 | 1.3.11（v1 已重构 community 布局），requirements 声明 `>=0.3` 且未锁版本 |
| 模型文件 | safetensors 已下载 7.8GB，位于 `root/models/models/XHToken--Spark-X2.5-4B/snapshots/master/`；**全磁盘无任何 .gguf** |
| 模型发现 | `check_model_local()` 实测返回 `missing`；代码期望路径 `root/models/XHToken/Spark-X2.5-4B/` 不存在 |
| llama.cpp / whisper.cpp | 同级无 llama.cpp（无转换/量化二进制）；`Memora/whisper.cpp/` 只有空的 `models/` 目录 |
| ffmpeg | 系统未安装，非 wav 音频无法转写 |
| 运行日志 | 无任何一次"执行全局复盘/问答"记录，**推理链路零运行证据** |
| 前端 | node_modules、.next 存在（dev 产物），无 standalone/静态导出 |
| 架构时效性 | Spark2_5 架构 llama.cpp 于 **2026-09-07 才合入支持**（模型 9 月 1 日开源），PyPI 预编译 wheel 大概率未含，需实测 |

---

## 1. P0：阻断性问题（不修，演示必翻车）

### P0-1 模型路径与 ModelScope 缓存布局不匹配 —— 模型"下了也看不见"
- `config.SPARK_MODEL_DIR = MODELS_ROOT/XHToken/Spark-X2.5-4B`（斜杠布局）；
- `snapshot_download(cache_dir=MODELS_ROOT)` 实际落盘为 `MODELS_ROOT/models/XHToken--Spark-X2.5-4B/snapshots/master/`（ModelScope/HF 标准缓存布局，`--` 分隔 + snapshots）。
- `ensure_gguf()` 调 `fetch_modelscope()` 后**丢弃了返回的真实路径**，回头仍检查错误目录，必然抛"下载后仍未找到 safetensors"。
- **修复**：以 `snapshot_download` 返回路径为准（或用 `modelscope.snapshot_download(..., local_dir=)` 指定平铺目录）；`check_model_local / discover_gguf / has_safetensors` 全部改为基于真实返回路径；转换输出文件名显式指定（当前用 `model_dir.name` 推导，snapshot 目录名是 `master`，会产出 `master-Q4_K_M.gguf`）。

### P0-2 默认后端三件套缺失 + 依赖声明双向漂移
- 实测缺 `llama-cpp-python`、`langchain-community`、`beautifulsoup4`；`modelscope` 未写进 requirements。
- requirements 全部 `>=` 不锁版本，langchain 已到 1.x（community 遗产拆入 langchain-classic / 独立集成包），全新机器按 requirements 安装后 import 即失败。
- **修复**：
  1. `pip freeze` 锁定一套验证过的版本（requirements-lock.txt），区分 core/voice/dev extras；
  2. 明确 langchain 选型：要么钉死 `langchain==0.3.x + langchain-community`，要么迁移到 1.x 正确导入路径；
  3. 补 `modelscope`、`beautifulsoup4`；
  4. 写 `scripts/check_env.py` 启动前自检（当前缺）。

### P0-3 没有 GGUF，而离线机无法完成"下载→转换→量化"
- 转换需要：含 Spark2_5 支持的 llama.cpp（2026-09-07 后 master）+ C++ 编译工具链 + llama-quantize；目标离线机三者都不会有。
- llama-cpp-python 的 PyPI wheel 是否含 Spark2_5 必须在打包机实测；不含则需源码构建。
- **修复（离线部署的核心决策）**：在联网打包机上一次性完成转换，**GGUF 随安装包分发，目标机零编译**：
  ```bash
  # 打包机（联网）
  python convert_hf_to_gguf.py <snapshot路径> --outfile spark-x2.5-4b-f16.gguf
  llama-quantize spark-x2.5-4b-f16.gguf spark-x2.5-4b-Q4_K_M.gguf Q4_K_M
  # 用 llama-cli 跑通一次推理再封包（架构支持的验收标准）
  ```
- **更稳的架构替代方案（推荐）**：直接随包分发 llama.cpp 官方预编译的 `llama-server.exe`（确认含 Spark2_5 的构建），后端统一走 OpenAI 兼容 HTTP（现有 SGLangBackend 改个 URL 即可复用），彻底绕开 llama-cpp-python 绑定/编译/PyInstaller 隐式库三大坑。

### P0-4 推理参数两处硬伤
- `n_gpu_layers=-1` 语义写反：llama.cpp 中 **0=全 CPU，-1=全部层上 GPU**。无 GPU 机器装到 CUDA 版 wheel 会直接报错。默认应 `0`。
- `n_ctx=196608` 在 8GB 机器必爆内存（测算见第 4 节），且未开启 KV 量化；代码也没有 `cache_type_k/v`。
- **修复**：`MEMORA_N_GPU=0`；默认 `n_ctx=32768~65536` + KV q8_0/q4_0；把 n_ctx、KV 量化做成 .env 显式项；启动日志打印预估内存。
- 另：`to_prompt_text(limit_chars=120_000)` 约 15-18 万中文 token，叠加 4096 输出，**本身就超过 196608 窗口**，会 context overflow；截断应按 token 估算并与 n_ctx 联动。

### P0-5 语音模块是空壳
- `whisper.cpp/` 无源码无二进制，`ggml-base.bin` 不存在，无 ffmpeg，`WHISPER_BIN` 硬编码 Windows `.exe`。
- **修复**：随包分发 `whisper-cli`（Win/macOS/Linux 三平台命名判断）+ `ggml-base.bin`（约 140MB）+ `ffmpeg.exe`（或明确只收 wav 并在前端拦截）。

### P0-6 "离线红线"名不副实
- `ENFORCE_OFFLINE=1`（实测默认开启）但 `ensure_gguf()`、`ensure_whisper_model()` **完全没有检查该开关**，模型缺失时照样发起 ModelScope 下载，与 README 宣传矛盾。
- **修复**：所有网络调用前强制检查开关；启动即注入 `HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 / MODELSCOPE_OFFLINE=1`；对 modelscope/langchain import 期外联做一次抓包审计并写进文档。

### P0-7 干净机端到端验收（目前 0%）
- 在一台**无 Python、无 Node、无编译器、断网**的干净 Windows 机器（或虚拟机）上，按交付包完成：安装 → 导入三平台样本 → 复盘 → 问答 → 语音 → 导出 → 清空，全程录屏。这是比赛演示的彩排，也是离线交付的唯一验收标准。

---

## 2. P1：竞赛硬核差距（一等奖与优秀奖的分水岭）

### P1-1 没有 RAG，"智能问答"名不副实
- 现状：QA 每次把全量对话塞进 prompt（`answer()`），无分片、无 embedding、无向量库；环境里已装 `sentence-transformers 5.6.1` 但代码完全没用。
- 会话只存内存 dict（重启丢失），vault 只加密存报告、不存对话；无法跨历史记录提问。
- **建议**：本地 embedding（bge-small-zh-v1.5，约 100MB，可转 ONNX 离线）+ faiss-cpu（纯 CPU、无服务）+ 消息级分片与元数据（发言人/时间）+ 答案引用溯源；Conversation 加密持久化进 vault，重启后可继续问答。

### P1-2 评测体系 / 消融实验完全空白（README 第九节自己挖了坑没填）
- 建 `eval/`：50-100 条多平台聊天记录标注集（合成生成+人工校验，覆盖待办/金额/时间/风险/多轮约定）+ 一小段会议录音。
- 指标：待办抽取 F1（含责任人/时间节点字段级准确率）、关键信息召回率、风险点召回、忠实度/幻觉率（无依据编造率）、Whisper 中文 CER、端侧首 token 延迟/吞吐/峰值内存/冷启动时间。
- 对比模型：Spark-X2.5-1.7B / 4B、MiniCPM5-2B、Qwen3 同级（你 `root/models` 里已经下了 MiniCPM5-2B、Qwen3.8-27B，可直接用）。
- **消融（核心卖点）**：全量长上下文 vs 分片 RAG；n_ctx=8k/32k/64k/196k；KV fp16 vs q8 vs q4；Q4_K_M vs Q5/Q8。产出"内存-精度-延迟"三线权衡表。这正是端侧场景最值得讲的故事，比单纯堆功能有说服力得多。

### P1-3 "Agent" 含量不足
- 现状是 3 个 PromptTemplate 的单轮流水线，无工具调用、无结构化约束、无自检回路、无流式。
- 报告四段结构靠正则切 Markdown，模型不按格式输出即崩；QA 路由同步阻塞，长复盘期间前端干等（FastAPI 线程池占满）。
- **建议**：llama.cpp grammar / JSON schema 约束输出为结构化对象（待办/风险直接入列表）；SSE 流式输出复盘过程；增加"待办-风险二次校验"自反思链；MAX_TOKENS_QA=1024 当前根本没生效（构造时固定 4096，代码注释自己承认），per-call 参数要打通。

### P1-4 隐私口径与实现不匹配（答辩被问会扣分）
- Fernet 密钥明文存 `data/vault.key`，与密文同目录：只能防"单文件被拷走"，防不住任何能读磁盘的人；索引 JSON 明文保存文件名/时间。
- `wipe_all()` 不清 `data/exports/`（明文 MD/PDF）和日志；QA 问题前 50 字会写进日志。
- **建议（二选一）**：改为用户口令经 PBKDF2/scrypt 派生密钥（口令不落盘），或如实改称"本地静态加密"；一键清空覆盖 exports/logs；日志对问题文本脱敏；**新增 PII 脱敏模块**（手机号/身份证/银行卡/姓名掩码，导入前可选）——对隐私主题是强加分项。

### P1-5 解析器鲁棒性
- 微信仅支持 PC 端 txt 一种形态；系统消息、撤回、引用、@、表情、图片/语音占位、多行续聊边界未处理；飞书正则对导出 HTML 结构脆弱；钉钉只适配单列 CSV。
- 测试用的是代码里构造的字符串，**没有真实脱敏样本文件**，也没有 `examples/`。
- **建议**：每平台收 3-5 份真实导出样本（脱敏后进仓库），建解析回归集；解析失败率本身也可作为评测指标。

---

## 3. P2：工程化与竞赛材料

- **打包形态**：新增 PyInstaller `.spec`（当前只在注释里"可内嵌"）或 python-embedded + wheelhouse 方案；前端 `next.config.ts` 加 `output: 'export'`（或 standalone），由 FastAPI StaticFiles 托管，免去目标机 Node。
- **一键脚本**：`start.bat`（端口检查→起后端→开浏览器）、`doctor.bat`/`/api/health/detail`（模型/GGUF/whisper/fffmpeg/内存/磁盘/端口逐项体检，给中文修复指引）。
- **离线依赖仓**：`pip download -r requirements-lock.txt -d wheelhouse --python-version 3.11 --platform win_amd64 --only-binary=:all:`；Node 侧直接分发构建产物；模型与二进制附 sha256。
- **零外联自证**：应用内"网络哨兵"（启动后对常见域名做连接并应全部失败的记录页）+ 防火墙/Wireshark 录屏教程，比口头"断网演示"有说服力。
- **PDF 导出**：当前逐行 Paragraph，待办勾选框/表格/嵌套列表不渲染、无页码页眉；补封面/页码/待办表格。
- **工程基建**：`.gitignore`（vault.key、.env、data/、node_modules、模型、whisper.cpp 源码）、LICENSE、Python 版本声明、FastAPI TestClient 集成测试、CI、版本号/构建信息进 health。
- **竞赛材料**：脱敏样例集、3-5 分钟演示视频与逐字脚本、架构白皮书（链路图+隐私设计+消融结论）、答辩 PPT、竞品对比（云端妙记/飞书/通义：隐私、离线、成本、安装包体积）、配置矩阵实测表（8G/16G、Intel/AMD、有无独显；冷启动、加载、1万/5万/10万字复盘耗时与峰值内存）。

---

## 4. 内存预算测算（"8GB 可跑"目前不成立）

口径：Spark2_5，36 层（9 层 full attention 承载长上下文，27 层 sliding_window=512），4 个 KV heads，head_dim=256；KV fp16 = 每 token 每 full 层 4KB；Q4_K_M 权重约 2.6GB；compute/运行时按 0.3GB 估。

| 配置 | full 层 KV | 合计估算内存 | 8GB 机器 |
|---|---|---|---|
| n_ctx=196608，KV fp16（当前默认） | 6.75 GB | **≈ 9.7 GB** | 必爆（swap 卡死） |
| n_ctx=196608，KV q8 | 3.38 GB | ≈ 6.3 GB | 边缘，不建议演示 |
| n_ctx=65536，KV fp16 | 2.25 GB | ≈ 5.2 GB | 可行 |
| n_ctx=32768，KV q8（建议默认） | 0.56 GB | ≈ 3.5 GB | 舒适 |

另需实测 CPU prefill 速度：19 万上下文在纯 CPU 4B 上可能达数十分钟，比赛演示不可接受；建议演示用例控制在 1-3 万字 + n_ctx=32768。

---

## 5. 建议的离线分发包结构（目标机零编译、零网络）

```
Memora-Offline-v1.0/
├─ start.bat                  # 一键启动（端口检查→后端→浏览器）
├─ doctor.bat                 # 环境自检
├─ app/                       # PyInstaller 产物（或 python-embedded + wheelhouse）
│   └─ memora-server.exe
├─ runtime/
│   ├─ llama-server.exe       # 含 Spark2_5 的官方构建（或内嵌 llama_cpp.pyd）
│   └─ models/spark-x2.5-4b-Q4_K_M.gguf   # 预转换，~2.6GB，附 sha256
├─ whisper/
│   ├─ whisper-cli.exe
│   └─ ggml-base.bin          # ~140MB
├─ ffmpeg/ffmpeg.exe          # 或前端限定 wav
├─ web/out/                   # next 静态导出，由后端 StaticFiles 托管
├─ data/                      # vault / exports / logs（空目录，运行时生成）
└─ README_离线安装.md          # 断网环境图文步骤 + 故障表
```

---

## 6. 两周排期建议

| 时间 | 目标 |
|---|---|
| D1-D2 | P0-1~P0-6 修通：路径、依赖锁定、GGUF 预转换验证、参数修正、离线开关、语音二进制 |
| D3-D4 | 离线包 v1 + 干净虚拟机断网端到端验收（P0-7） |
| D5-D7 | eval 数据集 + 指标脚本 + 模型对比 + 长上下文/RAG 消融（P1-1/P1-2） |
| D8-D9 | 结构化输出、SSE 流式、会话加密持久化、PII 脱敏（P1-3/P1-4） |
| D10-D11 | 解析真实样本回归、PDF 完善、doctor 自检、性能矩阵实测 |
| D12 | 桌面壳/安装器、零外联自证录屏 |
| D13-D14 | 白皮书、PPT、演示视频、答辩彩排 |

---

## 7. 值得保留的亮点（答辩主线）

1. 端侧 + 离线 + 隐私的选题切得准，Spark-X2.5 是 9 月新开源模型，时效性强；
2. 双后端抽象（内嵌 llama.cpp / 外部 OpenAI 兼容 server）、薄层 FastAPI + 核心包复用的分层干净；
3. 三平台解析自动嗅探 + 纯文本兜底、Fernet 静态加密、中文日志、.env 集中配置、批量复盘、MD/PDF 导出，产品闭环意识好；
4. README 的"隐藏坑记录""消融设想"说明工程判断在线——把消融从 README 变成代码和数据，就是一等奖材料。

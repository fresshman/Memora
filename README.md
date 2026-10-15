<div align="center">

<h1>🧠 Memora</h1>

<p><strong>端侧离线 · 隐私优先的对话智能复盘工具</strong></p>

<p>
<img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white">
<img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&amp;logoColor=white">
<img alt="Model" src="https://img.shields.io/badge/Model-Spark%20X2.5%204B%2F1.7B-FF6B35">
<img alt="Offline" src="https://img.shields.io/badge/Runs_100%25-Offline_%26_On__device-2ea44f">
<img alt="No torch/GPU" src="https://img.shields.io/badge/No-torch_%2F_GPU-999999">
<img alt="Tests" src="https://img.shields.io/badge/Tests-189%20passed-brightgreen">
<img alt="License" src="https://img.shields.io/badge/License-MIT-2ea44f">
</p>

<p>Spark-X2.5 端侧模型 ・ llama.cpp ・ 本地 bge-m3 + FAISS ・ FastAPI + Next.js</p>

<p>
<a href="README.en.md">English</a>
&nbsp;|&nbsp;
<strong>简体中文</strong>
</p>

</div>

---

<div align="center">

🎬 <strong>项目介绍短片 · 3 分 16 秒 · 全程真实操作录屏</strong>（<em>多平台导入 → PII 脱敏 → 流式复盘 → 对话问答 → 语音转写/声纹识别 → 跨会议行动项追踪 → 一键导出复盘包</em>）

<a href="video/memora-intro/renders/memora-intro.mp4">
<img src="docs/images/video_cover.png" alt="Memora 项目介绍短片" width="760">
</a>

▶️ 点击观看 / 下载：<a href="video/memora-intro/renders/memora-intro.mp4"><strong>memora-intro.mp4</strong></a>（1920×1080 · 30fps · MP4 · 约 23MB · 画面均为真实运行截图，无夸大演示）

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
- 🎙️ **语音会议全本地复盘**：上传 mp3 / m4a / wav / flac / ogg / opus / wma 等常见录音，经 ffmpeg 降噪与响度归一，
  本地 whisper.cpp 转写、**CAM++ 神经声纹自动识别说话人**，整理成「说话人 + 时间戳」标注记录，一键导出
  MD/TXT/SRT/PDF，或流式提炼结构化纪要。纯 CPU、无 torch。
- ✏️ **说话人重命名 + 转写人工校对**：把「说话人N」一键改成真实姓名（颜色与归属自动迁移），逐条修正转写文字；
  导出与「一键提炼纪要」均基于校对后内容，并可随时撤销全部修改。
- 🧬 **跨会话联系人声纹库**：给说话人重命名即把其声纹注册进本地联系人库（纯 JSON、数据不出设备）；后续新会议聚类后，
  系统会把高置信的主导者**自动认成老熟人**（真实多人会议主导者跨日相似度 0.90+），拿不准的保持「说话人N」由你一键正名，
  做到「宁漏认、不误认」；可在「联系人声纹库」弹窗查看、改名、删除。
- 🔴 **实时录音流式转写**：麦克风边说边出字，AudioWorklet 16kHz 采集 + WebSocket 实时增量转写与说话人归并，结束后整体重转写精修为完整记录，复用校对 / 导出 / 纪要；全程离线、低时延。
- ✅ **跨会议行动项追踪闭环**：复盘 / 纪要生成后，待办自动抽取为**结构化行动项**（标题 / 责任人 / 截止时间 / 来源会议 / 状态），自动去重归并、匹配本地联系人；后续会议一键「进展回顾」即可批量核对并**自动更新状态**（待跟进 / 进行中 / 已完成 / 已取消），动态标记逾期，把单次记录升级为事项落地追踪。
- 🧠 **Spark 思考档位一键切换**：暴露 Spark-X2.5 **官方特色**——「快速 / 深度思考」两档。快速档关闭思维链、低时延出结果；深度档开启思维链、处理复杂复盘，切换无需重建链路。
- 📦 **一键导出项目复盘包**：把**复盘报告 + 行动项清单 + 会议记录 + 问答记录 + 原始对话**打包成单个 zip（含索引 README），行动项始终取最新状态，便于归档、交接与复盘会分发。

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

## 🎙️ 语音会议链路（全程本地、纯 CPU）

上传会议录音，整条链路在设备内闭环，**数据不出设备**：

```text
音频（mp3/m4a/wav/flac/ogg/aac/wma/opus/amr…）
   │ ffmpeg 解码 16kHz mono：afftdn 降噪 + dynaudnorm 响度归一（soundfile 兜底）
   ▼
pywhispercpp（whisper.cpp 进程内）转写，输出带时间戳句子段（简体引导）
   │ 能量 VAD 仅统计有效语音（不门控转写）
   ▼
CAM++ 神经声纹 embedding（speakeronnx ONNX）+ AHC 凝聚聚类（自动定人数 / 可手填）
   ▼
标注会议记录（说话人 + 时间戳，同人相邻自动合并）
   ▼
✏️ 人工校对（重命名说话人为真实姓名、逐条修正转写，可一键撤销）
   ├── 一键导出 Markdown / TXT / SRT / PDF（基于校对后内容）
   └── SSE 流式提炼结构化纪要（结论 / 待办 / 关键信息 / 风险，基于校对后内容）
```

**说话人分离实测**（8 通道远场麦克风阵列，RTTM 金标准，frame-level DER + Hungarian 映射）

| 片段 | 发言特征 | 识别说话人 | DER | 说明 |
|---|---|---|---|---|
| FRONT（0–3 分钟） | 轮流发言、重叠 1.8%、句间有停顿 | **7 / 7** | **0.115** | 漏分 0、混淆 .115 |
| MID（10–13 分钟） | 语音占 93.7%、快速抢话、重叠 9.6% | 3 | 0.598 | 小孔径阵列（通道时延 ±0.12ms）无法空间分人、混响污染声纹 |

> **诚实的能力边界**：Memora 的目标场景是**手机 / 电脑近场录音、在线会议平台导出的已增强音频、正常轮流会议**（落在 FRONT 的"可用"区间）。
> 对"小孔径远场阵列 + 高重叠快速抢话"，已验证 5 种声纹模型 / 8 个通道 / 4 种前端均失效——这是硬件孔径与混响导致的研究性难题，而非算法或前端单点问题；近场、低重叠场景 DER 显著更低。

**ASR 模型档位**（ggml 官方在 HuggingFace，经 hf-mirror 下载；语音页 / 模型管理一键获取）

| 模型 | 大小 | 适用 |
|---|---|---|
| ggml-base.bin | ≈148MB | 干净近场、低配快速；远场会重复幻觉 |
| **ggml-small.bin（默认）** | ≈488MB | **远场实测连贯可用、8GB 友好** |
| ggml-large-v3-turbo.bin | ≈1.5GB | 质量优先、转写最准 |

**转写质量评测（CER/WER）与领域热词**

以 TextGrid 人工转写为金标准，对同一段 180s 真实会议录音计算**字错率 CER**（逐字编辑距离）与**词错率 WER**（jieba 分词）；文本先归一化（去标点 / 静音 / 噪声标记）。

| 配置 | CER | WER | 说明 |
|---|---|---|---|
| 无热词 | 37.65% | 46.41% | 仅简体引导 |
| **领域热词表** | **26.45%** | **35.73%** | **CER 相对 ↓29.7%、WER 相对 ↓23.0%** |

- 热词表 `memora/whisper/hotwords.txt` 在转写时作为 `initial_prompt` 前缀注入，内置**组织职务 / 会议流程 / 场地物资节目**三组通用中文会议热词；可自行增删、保存即生效，清空文件即关闭。
- 实测：正常会议语境下「运动场、气球、学生部、策划、节目、合唱、伴舞、服装、道具、负责人、副部长」等专名被正确识别；剩余错误集中在开场连续报数的编号（如「零零二」，声学特殊）与个别近音词（元旦→元代、赞助→钻柱、红地毯→房地产），属于 small 模型 + 远场的能力边界，近场或 large-v3-turbo 会进一步降低。
- 复现：`python scripts/eval_asr.py --textgrid <X.TextGrid> --clip <clip.wav> --t0 30 --t1 210 --hotwords memora/whisper/hotwords.txt`；结果见 `evals/results/asr_small_*.json`。
**⑥ 语音会议记录** —— 自动识别说话人并按时间戳着色，连贯转写，可一键导出四种格式。

<p><img src="docs/images/07_voice.png" width="840"></p>

**⑦ 语音会议纪要** —— 由 Spark-X2.5 基于标注记录流式提炼，四段结构并引用对应说话人。

<p><img src="docs/images/09_voice_minutes.png" width="840"></p>

### 🔴 实时录音流式转写（边说边出字）

除了上传录音文件，Memora 还支持**麦克风实时录音**：边说边出字、结束后一键整理为完整会议记录。

- **实时段（低时延）**：浏览器 AudioWorklet 以 16kHz 采集，每约 1s 经 WebSocket 上送；后端每攒满约 3s 即用常驻 ASR 模型转写，CAM++ 声纹与已出现说话人实时比对归并，快速回推 delta 上屏。
- **最终段（保质量）**：点击「结束并整理」后，对整场录音**一次性重转写 + 整体 AHC 说话人精修**（复用上传链路），得到连贯、不丢词、可校对 / 导出 / 提炼的完整记录——实时窗口的切词瑕疵不影响最终结果。
- **协议**：WebSocket `/api/voice/stream`，消息 `start / chunk / stop` ↔ `ready / delta / final / error`；音频为 16kHz mono Int16 PCM（base64）。
- ASR 常驻模型进程级懒加载，避免每个窗口重复加载；CPU 重活全部进入线程池，不阻塞事件循环。

**⑧ 实时录音** —— 「上传录音文件 / 实时录音」一键切换，录音中红点计时、电平条、实时出字；结束即整理为标注记录，复用校对 / 导出 / 纪要全部下游。

<p><img src="docs/images/10_voice_live.png" width="840"></p>

### 🧬 跨会话联系人声纹库（重命名即注册）

普通语音转写工具"每场会议都从零开始"，同一个人在不同会议里被反复标成「说话人N」。Memora 把**姓名与声纹**沉淀为可跨会议复用的本地联系人库：

- **重命名即注册**：在标注记录里把「说话人N」改成真实姓名，系统自动把该簇的 CAM++ 声纹写入 `data/contacts.json`（同一人多次正名会聚合多样本、越用越准）。
- **新会议自动认人**：新录音聚类后，每个簇的质心与联系人库逐一比对，命中即标注为该联系人并给出匹配置信度；界面上以 ✓ 标识，与需正名的簇明显区分。
- **零误认优先（保守策略）**：以真实多人会议（train_L）校准——发言充分的主导者跨日质心稳定在 **0.90+**，而声学相近的未注册者约 0.82；默认匹配阈值取 **0.85**，**拿不准的一律保持「说话人N」，宁漏认也不张冠李戴**。漏认只需一次正名，误认却会误导整场记录。
- **联系人管理**：顶部「联系人声纹库」弹窗列出全部联系人（相遇次数、最近相遇时间），支持改名与删除；全部数据保存在本地 JSON、数据不出设备。

**真机跨会议结果（会议1 注册 → 会议2 识别，真实多人会议）**：

| 类型 | 数量 | 说明 |
| --- | --- | --- |
| 主导者正确识别 | 3 | 003 / 004 / 001，跨日相似度 0.900 / 0.949 / 0.914 |
| 误认（张冠李戴） | **0** | 阈值 0.85 拦截 |
| 漏认（保持 generic） | 3 | 声学相近的未注册者 006(0.82)、发言少的过分割小簇 |

> **已知边界与闭环**：① 同性别、声学确实相近（train_L 两位女声，CAM++ 相似度 0.82）且未注册者，需一次正名；② 快速轮流被过分割的小簇、发言极少者质心不稳，不强行识别——这些都会以「说话人N」呈现，由你在界面**正名（即注册）或合并**，声纹库随校对不断增强。跨会议的"事项（待办/决议）归属"列为后续路线。

## ✅ 跨会议行动项追踪闭环（从"看清"到"办完"）

一次复盘只解决"看清这次沟通"，但工作真正的闭环是**事有人办、按时办完**。Memora 把每次复盘产生的待办，
升级为可跨会议持续追踪的**行动项**，并与本地联系人库打通：

```text
复盘 / 纪要生成
   │ 报告中的待办被确定性抽取为结构化行动项（不额外调用模型，失败不阻塞）
   ▼
自动入库（标题 / 责任人 / 截止时间 / 来源会议）
   │ ① 相似待办去重归并、补全责任人与截止时间
   │ ② 责任人命中本地联系人库 -> 关联 contact_id
   ▼
后续会议（新记录）
   │ 一键「进展回顾」：一次 LLM 调用，批量核对全部未完成行动项
   ▼
自动更新状态 + 记录历史（谁、何时、依据哪句话）
   │ 截止时间按"今天"动态判定逾期（不改动数据）
   ▼
行动项看板（待跟进 / 进行中 / 已完成 / 已取消）── 手动改状态 / 完成 / 按责任人筛选
   │
   └── 一键导出「项目复盘包」（zip，含最新行动项清单）
```

**状态机**：`待跟进（open）→ 进行中（in_progress）→ 已完成（done）`；任意阶段可 `已取消（cancelled）`。
每次状态变更都写入 `history`（时间、原状态、新状态、依据来源），全程留痕。

**进展识别规则**：进展判断**强制关闭思维链**（省算力、更快），模型对每条行动项输出状态：
「已完成 / 已交付 / 已通过」→ done；「推进中 / 跟进中 / 有进展」→ in_progress；「已取消 / 不再需要」→ cancelled；
未提及 / 无法识别 → **保持原状、不臆改**。再由 `MEMORA_ACTION_AUTO` 决定是否自动落库（默认开）。

**真机实测（1.7B 快速档，会议1 布置 3 项 → 会议2 反馈进展）**：

| 模型 | 进展判断 | 说明 |
|---|---|---|
| Spark-X2.5-1.7B | 链路完全打通，状态判断有偏差 | 把"已完成并提交"误判为进行中、个别未提及项误判为进行中，**4GB 内存可跑的兜底档** |
| **Spark-X2.5-4B（推荐）** | 状态判断更准确 | 复杂进展 / 多事项核对的主力，体现官方模型档位差异 |

> 进展回顾是一次 LLM 调用，故设计为**复盘后手动触发**（点「进展回顾」），而非全自动，以节省 CPU；
> 行动项数据保存在本地 `data/action_items.json`（原子写、数据不出设备），复盘包中的行动项清单始终取最新状态。

## 🧠 思考档位与项目复盘包

- **思考档位（Spark 官方特色）**：Spark-X2.5 原生支持可配置的思考档位。Memora 在复盘 / 语音 / 首页均暴露切换：
  - **快速档（fast，默认）**：经 `chat_template_kwargs.enable_thinking=False` 关闭思维链，流式增量即正文，低时延；
  - **深度档（deep）**：开启思维链处理复杂 / 高难度复盘，`done` 事件自动剥离思维链、只返回干净正文，并自动放大生成长度上限（复盘 8192 / 问答 4096）。
  档位在请求级透传，切换无需重建模型或链路；持久化由 `MEMORA_THINKING` 控制。
- **项目复盘包（zip）**：`POST /api/export/package` 用标准库 `zipfile` 打包，包含：
  `README.md`（索引 + 行动项概览）、`01_复盘报告.md`、`02_行动项清单.md`（始终最新）、
  `03_会议记录.md`（语音）、`04_问答记录.md`（QA）、`05_原始对话.md`（可选）；
  有则收录、无则跳过，纯标准库实现、零额外依赖。

## 🖥️ 功能页面

| 页面 | 路径 | 说明 |
|---|---|---|
| 对话复盘（首页） | `/` | 粘贴 / 上传聊天记录 → PII 预览 → 流式生成结构化报告，一键导出 |
| 智能问答 | `/qa/` | 基于全部对话追问，回答带原文引用 |
| 模型管理 | `/models/` | 双模型推荐、本地状态检测、ModelScope 一键下载、在线切换 |
| 批量复盘 | `/batch/` | 多份记录批量处理与汇总 |
| 语音会议复盘 | `/voice/` | 上传文件或麦克风实时录音，多格式转写 + 说话人分离（可重命名、人工校对），标注记录一键导出或提炼纪要 |
| 行动项看板 | `/action/` | 跨会议行动项四状态看板、统计与逾期标识、按责任人筛选、手动改状态、进展回顾、思考档位切换、导出复盘包 |
| 历史记录 | `/history/` | 本地加密存储的复盘历史 |

## 📸 界面预览

**① 导入对话** —— 粘贴或上传聊天记录，自动嗅探编码与平台格式。

<p><img src="docs/images/01_home.png" width="720"></p>

**② 本地解析与 PII 脱敏** —— 发言人角色化为成员 A/B，手机 / 邮箱 / 人名在送入模型前替换为占位符，映射仅存本机、可一键还原。

<p><img src="docs/images/02_pii.png" width="720"></p>

**③ 结构化复盘报告** —— 核心结论 / 待办（含责任人与时间节点）/ 关键信息 / 风险提示四段，会议决定确定性归位。

<p><img src="docs/images/03_report.png" width="500"></p>

**④ 智能问答** —— 基于全部对话检索增强，回答附原文引用，未讨论即明说「未讨论」。

<p><img src="docs/images/04_qa.png" width="720"></p>

**⑤ 模型管理 / 批量复盘 / 历史记录**

<table>
<tr>
<td align="center"><img src="docs/images/05_models.png" width="350"></td>
<td align="center"><img src="docs/images/06_batch.png" width="350"></td>
</tr>
<tr>
<td align="center"><img src="docs/images/08_history.png" width="350"></td>
<td></td>
</tr>
</table>

**⑥ 行动项看板** —— 跨会议行动项按「待跟进 / 进行中 / 已完成 / 已取消」分列，顶部统计总数与逾期，卡片含责任人（挂联系人）、截止时间与来源；支持按责任人筛选、一键改状态 / 完成、进展回顾与导出复盘包。

<p><img src="docs/images/11_action_board.png" width="840"></p>

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

**准备语音链路（可选）**：

```bash
conda install ffmpeg                                   # 或下载 ffmpeg 静态构建放 tools/ffmpeg
pip install pywhispercpp speakeronnx onnxruntime       # 已含在 requirements.txt
# 启动后进入「语音会议复盘」上传录音；缺失 ASR 模型时按提示从 hf-mirror 一键下载
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
        │
会议录音(mp3/m4a/wav…)
        │  ffmpeg 解码/降噪·响度 → whisper 转写 → CAM++ 说话人分离
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
│   ├── action_items.py     #   跨会议行动项：抽取 / 去重归并 / 进展回顾 / 逾期
│   ├── report/             #   报告结构化与「会议决定归位」（评测与产品同一口径）
│   ├── prompts/            #   提示词模板
│   ├── backend/            #   llama-server 子进程后端 + 可选 SGLang 后端
│   ├── storage/            #   Fernet 本地加密
│   ├── whisper/            #   语音：解码/转写/说话人分离/会议记录
│   ├── model_fetch.py      #   模型获取状态机（官方 GGUF 下载 + safetensors 转换兜底）
│   ├── exporter.py         #   Markdown / PDF 导出 + 项目复盘包（zip）
│   └── batch.py            #   批量复盘
├── server/                 # FastAPI：单端口 8000，web/out 同源托管
│   └── routes/             #   review / qa / actions / models / records / export / voice / health
├── web/                    # Next.js + React + Tailwind（app 页面 + out 静态产物）
├── evals/                  # 评测集、指标、worker/runner、单文件 HTML 报告
├── samples/                # 微信/钉钉/飞书真实解析样本库
├── scripts/                # doctor / prepare_model / start.bat / build_offline.ps1 / e2e
├── tests/                  # 189 项 pytest（不加载模型、不联网）
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
| `MEMORA_ASR_MODEL` / `MEMORA_ASR_VAD` | `ggml-small.bin` / `0` | ASR 模型档位 / 内置 VAD（默认关，空模型会崩溃） |
| `MEMORA_SPK_EMBED` / `MEMORA_SPK_SIM` | `campplus-zh-en` / `0.5` | 声纹模型 / AHC 聚类相似度阈值（宁可过分割、不连锁） |
| `MEMORA_CONTACT_THR` | `0.85` | 跨会议认人匹配阈值；近场同设备追召回可降到 0.75～0.8 |
| `MEMORA_THINKING` | `fast` | 思考档位：`fast`（快速、关闭思维链）/ `deep`（深度思考） |
| `MEMORA_ACTION_TRACK_MAX` | `20` | 进展回顾一次批量核对的未完成行动项上限 |
| `MEMORA_ACTION_AUTO` | `1` | 进展回顾后是否自动更新状态（0 = 仅给出建议、不改动） |

## 🧪 测试与评测复现

```bash
python -m pytest tests/ -q                          # 189 项单测：不加载模型、不联网
# 真机离线端到端（需已放置模型，24 项）
set MEMORA_ENFORCE_OFFLINE=1 && python scripts/e2e_offline_check.py
# 全量评测与消融（需模型，耗时较长，贪心解码可复现，断点续跑）
cd evals && python runner.py
# ASR 转写 CER/WER 与热词对比（需 TextGrid 金标准 + 模型）
python scripts/eval_asr.py --textgrid <X.TextGrid> --clip <clip.wav> --t0 30 --t1 210
```

## 🗺️ 路线图

- [x] 多平台解析、PII 脱敏、本地 RAG、SSE 流式、模型一键下载、离线发布包、评测与消融
- [x] 语音会议链路：多格式转写、CAM++ 说话人分离、标注记录导出与纪要（分场景 DER 实测）
- [x] 说话人重命名 + 转写人工校对，导出 / 纪要基于校对后内容（端到端真机验证）
- [x] 实时录音流式转写：麦克风边说边出字，结束整体重转写精修，复用校对 / 导出 / 纪要（端到端真机验证）
- [x] 跨会话联系人声纹库：重命名即注册、新会议自动认人（主导者跨日零误认），联系人管理弹窗（真机校准）
- [x] 跨会议行动项追踪闭环：待办自动入库 / 去重归并 / 关联联系人、进展回顾批量核对并自动更新状态、逾期标记、看板（真机验证）
- [x] Spark 思考档位切换（快速 / 深度，官方特色）与一键导出项目复盘包（报告 + QA + 记录 + 行动项 zip）
- [ ] 声学相近者的语义辅助消歧；进展回顾在复盘后的自动触发策略
- [x] ASR 转写 CER/WER 量化评测 + 可编辑领域热词表（热词使 CER 37.65%→26.45%）
- [ ] ffmpeg / ASR / 声纹模型随离线包分发（当前按指引下载）
- [ ] PyInstaller / WebView 桌面 EXE 一键安装包
- [ ] 更多 IM / 会议平台导出格式解析
- [ ] 8GB / 16GB、Intel / AMD、有无独显的配置矩阵实测

## 🙏 致谢与第三方许可

Memora 站在开源社区的肩膀上。下列**第三方开源组件、模型与数据的著作权始终归各自作者 / 权利人所有**，
本项目仅以依赖调用或指引下载的方式使用它们，**不主张、不转让、不重新分发**其任何权利；使用者须继续遵守其各自许可证。

**开源软件依赖**

| 组件 | 用途 | 许可证 |
|---|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 端侧 GGUF 推理引擎（llama-server） | MIT |
| [LangChain](https://github.com/langchain-ai/langchain) / langchain-core / langchain-openai | Agent 与链路编排 | MIT |
| [FastAPI](https://github.com/fastapi/fastapi) / [Uvicorn](https://github.com/encode/uvicorn) | 后端 HTTP / ASGI | MIT / BSD-3-Clause |
| [faiss-cpu](https://github.com/facebookresearch/faiss) / [NumPy](https://numpy.org) | 本地向量检索 / 数值计算 | MIT / BSD-3-Clause |
| [pandas](https://pandas.pydata.org) / [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) | 解析辅助 | BSD-3-Clause / MIT |
| [chardet](https://github.com/chardet/chardet) | 编码嗅探（以库形式动态调用、未修改） | LGPL-2.1-or-later |
| [ModelScope SDK](https://github.com/modelscope/modelscope) | 模型一键下载 | Apache-2.0 |
| [cryptography](https://github.com/pyca/cryptography) | Fernet 本地加密 | Apache-2.0 OR BSD-3-Clause |
| [python-multipart](https://github.com/Kludex/python-multipart) / [python-dotenv](https://github.com/theskumar/python-dotenv) / [reportlab](https://www.reportlab.com) | 表单 / 配置 / PDF 导出 | Apache-2.0 / BSD-3-Clause / BSD-3-Clause |
| [Next.js](https://nextjs.org) / [React](https://react.dev) / [Tailwind CSS](https://tailwindcss.com) | 前端框架与样式 | MIT |
| [pytest](https://github.com/pytest-dev/pytest) | 测试框架 | MIT |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) / [pywhispercpp](https://github.com/absadiki/pywhispercpp) | 本地语音转写引擎 / Python 绑定 | MIT |
| [speakeronnx](https://pypi.org/project/speakeronnx/) / [onnxruntime](https://github.com/microsoft/onnxruntime) | CAM++ 说话人声纹 / ONNX 推理 | 以官方仓库为准 / MIT |
| [SciPy](https://scipy.org) / [scikit-learn](https://scikit-learn.org) / [soundfile](https://python-soundfile.readthedocs.io) | 聚类降级 / 音频兜底 | BSD-3-Clause |
| [ffmpeg](https://ffmpeg.org) | 音频解码 / 降噪 / 响度归一 | LGPL-2.1-or-later 或 GPL（取决于构建，动态调用） |

**模型与数据（不随代码仓库分发）**

| 资源 | 权利人 / 来源 | 许可 |
|---|---|---|
| Spark-X2.5-4B / 1.7B（含 GGUF 转换版） | XHToken（[ModelScope](https://modelscope.cn/models/XHToken/Spark-X2.5-4B-GGUF)） | 以模型官方页面许可为准 |
| bge-m3（GGUF） | BAAI / gpustack（[ModelScope](https://modelscope.cn/models/gpustack/bge-m3-GGUF)） | 以模型官方页面许可为准 |
| Whisper ggml ASR 模型 | OpenAI / ggerganov（[HuggingFace](https://huggingface.co/ggerganov/whisper.cpp)） | MIT（权重以官方为准） |
| CAM++ / ERes2Net 声纹模型 | ModelScope / speakeronnx（campplus-zh-en） | Apache-2.0（以模型卡为准） |

> 本仓库**不内置、不重新分发**上述模型权重与 llama.cpp 二进制，需使用者自行从官方渠道获取；
> 许可证信息以各项目官方 `LICENSE` 为准。若你二次分发 Memora，请自行确保同时满足所引用组件与模型的许可要求。

## 📄 许可证

本项目的**原创源代码与文档**基于宽松的 [MIT 许可证](LICENSE) 发布：可自由使用、修改、合并、发表、分发乃至商用，
唯一条件是在所有副本中保留版权声明与本许可声明；软件按“现状”提供，作者不承担任何担保责任。

- MIT 许可证**仅覆盖 Memora 作者编写的原创代码与文档**，**不改变、不覆盖**上表任何第三方组件与模型的许可；
- 这是对商业友好、且与 MIT / BSD / Apache / LGPL（动态调用）等常见开源许可**兼容**的选择，不会侵害所引用开源项目的权利；
- 若对模型权重的商用许可有疑问，请以 Spark-X2.5、bge-m3 官方页面的授权条款为准。

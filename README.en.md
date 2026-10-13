<div align="center">

<h1>🧠 Memora</h1>

<p><strong>On-device, Offline-first &amp; Privacy-preserving Conversation Review</strong></p>

<p>
<img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white">
<img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&amp;logoColor=white">
<img alt="Model" src="https://img.shields.io/badge/Model-Spark%20X2.5%204B%2F1.7B-FF6B35">
<img alt="Offline" src="https://img.shields.io/badge/Runs_100%25-Offline_%26_On__device-2ea44f">
<img alt="No torch/GPU" src="https://img.shields.io/badge/No-torch_%2F_GPU-999999">
<img alt="Tests" src="https://img.shields.io/badge/Tests-150%20passed-brightgreen">
<img alt="License" src="https://img.shields.io/badge/License-MIT-2ea44f">
</p>

<p>Spark-X2.5 on-device LLM ・ llama.cpp ・ local bge-m3 + FAISS ・ FastAPI + Next.js</p>

<p>
<strong>English</strong>
&nbsp;|&nbsp;
<a href="README.md">简体中文</a>
</p>

</div>

---

> A **fully offline, privacy-first** tool that turns long work-group chats into structured meeting minutes.
> It packs the **Spark-X2.5 on-device small model + local Retrieval-Augmented Generation (RAG)** onto an ordinary
> **8GB-RAM Windows PC**. **Your data never leaves the machine** — yet hundreds or thousands of messages are distilled
> into **Key Decisions / Action Items / Risks**, with follow-up Q&amp;A grounded in the full conversation.
>
> **No GPU, no torch, no network required** — a single local folder that replaces cloud meeting-minutes SaaS
> (which force you to upload sensitive chats).

---

## ✨ Why Memora

Cloud minute-taking is powerful, but industrial chats contain **customer data, release windows, incident details and
owners** that should not be uploaded. Meanwhile, on-device 1.7B/4B models struggle with context length, lost-in-the-middle
and unstable structure. Memora solves this with an all-local, measurable and reproducible pipeline:

- 🔒 **Truly offline & private**: `MEMORA_ENFORCE_OFFLINE=1` by default — the app **never reaches the network**, even when
  a model is missing; inference binds only to `127.0.0.1`. Phone / ID / bank card / email / license plate / passport /
  person names are **redacted on-device before reaching the model**; the mapping lives only in memory and can be restored
  with one click, while stored records are Fernet-encrypted.
- 📚 **Long conversations without losing context (local RAG)**: short chats are fed **whole, with zero loss**; long chats are
  chunked and retrieved with on-device **bge-m3 embeddings + FAISS** (multi-way semantic recall + timeline skeleton), guarded
  by a **hard context budget** so the model window is never exceeded — instead of naively dropping the oldest messages.
  Pure CPU, no torch.
- 🧾 **Structured review & grounded Q&amp;A**: a fixed four-section report (Decisions / Action Items / Risks / Key Information),
  with meeting **time / venue / arrangements deterministically re-homed** into the decisions section. Q&amp;A retrieves over the
  whole conversation, answers carry **verbatim citations**, and unmentioned questions are explicitly answered as "not discussed".
- 💬 **Real multi-platform parsing**: WeChat (txt, including GBK), DingTalk (csv) and Feishu/Lark (html) exports, with automatic
  encoding/format detection and 10 real parsing samples.
- ⚡ **Product-grade experience**: **token-by-token SSE streaming**, a Next.js SPA, single-origin deployment on one port
  (end users need **no Node.js**), Markdown/PDF export and batch review.
- 🧩 **One-click model management**: the home and model pages explicitly recommend **Spark-X2.5-4B / 1.7B**, detect whether the
  model exists locally, and — after a confirmation dialog — download the official Q4_K_M GGUF automatically via
  **ModelScope `snapshot_download`**, ready to use with no manual conversion.
- 🎙️ **Fully local voice-meeting review**: upload mp3 / m4a / wav / flac / ogg / opus / wma and other common recordings;
  ffmpeg denoises and normalizes loudness, local whisper.cpp transcribes, and a **CAM++ neural voiceprint automatically
  identifies speakers**. The result is an annotated record (speaker + timestamps), exportable to MD/TXT/SRT/PDF or distilled
  into structured minutes via streaming. Pure CPU, no torch.
- ✏️ **Speaker renaming + transcript proofreading**: rename "Speaker N" to a real name (colors and ownership migrate automatically)
  and edit each transcript line; export and "distill minutes" use the proofed content, and all edits can be undone in one click.
- 🧬 **Cross-session contact voiceprint library**: renaming a speaker registers their voiceprint in a local contact library (plain JSON, data never leaves the device). In later meetings, high-confidence dominant speakers are **recognized as familiar people automatically** (dominant speakers show 0.90+ cross-day similarity on real multi-party meetings); uncertain ones stay "Speaker N" for you to name once — "rather miss than misidentify". View, rename or delete contacts in the library dialog.
- 🔴 **Live recording & streaming transcription**: watch the transcript appear as you speak. AudioWorklet captures 16kHz audio and streams it over WebSocket for incremental transcription and speaker assignment; on stop, the whole session is re-transcribed and refined into a final record, reusing proofreading / export / minutes. Fully offline, low latency.

## 📊 Evaluation & Ablation (measured, not claimed)

A built-in benchmark of 50 synthetic conversations (30 short + 20 long) with 346 probing Q&amp;A pairs. Greedy decoding
(`MEMORA_TEMP=0`) makes results reproducible. Metrics cover **recall & precision for action items / risks / decisions,
risk extraction completeness, Q&amp;A evidence hit rate and hallucination rate**, exported as a single-file HTML report.

**Main leaderboard (Spark-X2.5-4B, Q4_K_M)**

| Scenario | Action recall | Risk recall | Decision recall | Risk completeness | QA evidence hit | Hallucination |
|---|---|---|---|---|---|---|
| Short chat · full context (n=30) | 0.928 | 0.967 | **0.900** | 0.983 | 1.000 | **0** |
| Long chat · local RAG (n=20) | 0.900 | 0.942 | **0.908** | 0.958 | 1.000 | **0** |

**Long-context strategy ablation (n=6 per group)**

| Strategy | Action / Risk recall | QA evidence hit | Verdict |
|---|---|---|---|
| 4B full context (exceeds window) | 0.250 / 0.250 | 0.000 | Breaks down, ~639s, unusable |
| 4B rule-based timeline compression | 0.944 / 0.917 | 1.000 | Fallback when no embedding model |
| **4B local RAG (bge-m3 + FAISS)** | **0.900 / 0.942** | **1.000 | **Best recall & usability — the default** |
| 1.7B local RAG (ultra-low-resource) | 0.694 / 0.611 | 0.333 | Runs in 4GB RAM; weaker Q&amp;A |

> Takeaway: local RAG rescues long conversations from the full-context failure (recall 0.25, QA 0) back to
> **0.90+ recall, QA evidence hit 1.0 and zero hallucination**. Full results: `evals/results/final/report.html`.

## 🎙️ Voice Meeting Pipeline (fully on-device, pure CPU)

Upload a meeting recording and the whole pipeline stays closed on the device — **data never leaves the machine**:

```text
Audio (mp3/m4a/wav/flac/ogg/aac/wma/opus/amr…)
   │ ffmpeg decodes to 16kHz mono: afftdn denoise + dynaudnorm loudness normalization (soundfile fallback)
   ▼
pywhispercpp (in-process whisper.cpp) transcribes into timestamped sentence segments (Simplified-Chinese hint)
   │ energy VAD only measures speech duration (does not gate transcription)
   ▼
CAM++ neural voiceprint embeddings (speakeronnx ONNX) + AHC agglomerative clustering (auto speaker count / manual)
   ▼
Annotated meeting record (speaker + timestamps; adjacent same-speaker segments auto-merged)
   ▼
✏️ Manual proofreading (rename speakers to real names, edit transcript lines; one-click undo)
   ├── one-click export to Markdown / TXT / SRT / PDF (uses the proofed content)
   └── SSE-streamed structured minutes (Decisions / Action items / Key info / Risks; uses the proofed content)
```

**Speaker-diarization measurements** (8-channel far-field microphone array; RTTM ground truth; frame-level DER + Hungarian mapping)

| Segment | Speaking pattern | Speakers found | DER | Note |
|---|---|---|---|---|
| FRONT (0–3 min) | Turn-taking, 1.8% overlap, inter-sentence pauses | **7 / 7** | **0.115** | 0 missed, .115 confusion |
| MID (10–13 min) | 93.7% speech, rapid crosstalk, 9.6% overlap | 3 | 0.598 | Small-aperture array (±0.12ms inter-channel delay) cannot separate spatially; reverb contaminates voiceprints |

> **Honest capability boundary**: Memora targets **near-field phone/PC recordings, already-enhanced audio exported from
> online meeting platforms, and normal turn-taking meetings** (the "usable" FRONT range). For "small-aperture far-field arrays
> + high-overlap rapid crosstalk", 5 voiceprint models / 8 channels / 4 front-ends all failed — a research-grade problem caused
> by hardware aperture and reverb, not a single algorithm/frontend issue. Near-field, low-overlap scenarios have much lower DER.

**ASR model tiers** (ggml officially on HuggingFace, downloaded via hf-mirror; one-click from the voice/model pages)

| Model | Size | Best for |
|---|---|---|
| ggml-base.bin | ~148MB | Clean near-field, low-spec/fast; hallucinates on far-field |
| **ggml-small.bin (default)** | ~488MB | **Coherent on far-field in tests, 8GB-friendly** |
| ggml-large-v3-turbo.bin | ~1.5GB | Best quality, most accurate transcription |

**Transcription quality (CER/WER) and domain hotwords**

Using the human TextGrid transcription as ground truth, we compute the **Character Error Rate (CER)** (char-level edit distance) and **Word Error Rate (WER)** (jieba-tokenized) on the same 180s real meeting clip; text is normalized first (punctuation / silence / noise markers removed).

| Configuration | CER | WER | Note |
|---|---|---|---|
| No hotwords | 37.65% | 46.41% | Simplified-Chinese prompt only |
| **Domain hotwords** | **26.45%** | **35.73%** | **CER down 29.7% rel., WER down 23.0% rel.** |

- The hotword list `memora/whisper/hotwords.txt` is injected as an `initial_prompt` prefix, bundling three groups of general Chinese meeting hotwords (organization/titles, meeting/procedure, venue/supplies/programs); edit freely and it takes effect on save (an empty file disables it).
- In normal meeting context, proper terms such as "sports field, balloons, student department, planning, program, chorus, dance backup, costumes, props, owner, vice-minister" are recognized correctly. Remaining errors are concentrated in the opening roll-call numbers (e.g. "002", acoustically unusual) and a few near-homophones (New-Year gala, sponsorship, red carpet) — the capability limit of the small model on far-field audio; near-field or large-v3-turbo reduces these further.
- Reproduce: `python scripts/eval_asr.py --textgrid <X.TextGrid> --clip <clip.wav> --t0 30 --t1 210 --hotwords memora/whisper/hotwords.txt`; see `evals/results/asr_small_*.json`.
**⑥ Voice meeting record** — speakers are auto-identified and color-coded by timestamp; coherent transcription; one-click export in four formats.

<p><img src="docs/images/07_voice.png" width="840"></p>

**⑦ Voice meeting minutes** — Spark-X2.5 distills the annotated record via streaming into four sections, citing the speakers.

<p><img src="docs/images/09_voice_minutes.png" width="840"></p>

### 🔴 Live Recording & Streaming Transcription

Besides uploading a recorded file, Memora supports **live microphone recording**: the transcript appears as you speak and is turned into a complete meeting record on stop.

- **Real-time (low latency)**: the browser AudioWorklet captures 16kHz audio and streams it over WebSocket roughly every second. Once about 3 seconds accumulate, the backend transcribes with a resident ASR model and assigns speakers in real time by comparing CAM++ embeddings against known speakers, pushing deltas to the UI.
- **Final (quality)**: on "Stop & organize", the whole session is **re-transcribed in one pass and refined with global AHC diarization** (reusing the upload pipeline), producing a coherent, lossless record that can be proofread / exported / distilled — window-boundary artifacts do not affect the final result.
- **Protocol**: WebSocket `/api/voice/stream`, messages `start / chunk / stop` ↔ `ready / delta / final / error`; audio is 16kHz mono Int16 PCM (base64).
- The resident ASR model is a process-level lazy singleton (no re-loading per window); all CPU-heavy work runs in a thread pool without blocking the event loop.

**⑧ Live recording** — switch between "Upload audio file / Live recording" with one click; during recording see a pulsing red dot, timer, level bars and real-time text; on stop get an annotated record that reuses proofreading / export / minutes.

<p><img src="docs/images/10_voice_live.png" width="840"></p>

### 🧬 Cross-session Contact Voiceprint Library (rename = register)

Most transcription tools "start from scratch every meeting" — the same person is repeatedly labeled "Speaker N". Memora stores **names and voiceprints** as a reusable local contact library:

- **Rename = register**: changing "Speaker N" to a real name writes that cluster's CAM++ voiceprint to `data/contacts.json` (repeated naming aggregates multiple samples and gets better over time).
- **Automatic recognition in new meetings**: after clustering a new recording, each cluster centroid is compared against the library; a match is labeled with that person and a confidence score, marked with a ✓ to distinguish it from clusters needing a name.
- **Zero misidentification first (conservative)**: calibrated on real multi-party meetings (train_L) — dominant speakers with sufficient speech have stable cross-day centroids at **0.90+**, while an unregistered acoustically-similar speaker is around 0.82; the default threshold is **0.85**, so **anything uncertain stays "Speaker N" — rather miss than misidentify**. A miss costs one rename; a misidentification misleads the whole record.
- **Contact management**: the "Contact voiceprint library" dialog lists all contacts (meetings count, last met), with rename and delete; everything stays in local JSON, data never leaves the device.

**Real cross-meeting results (meeting 1 registered -> meeting 2 recognized):**

| Type | Count | Detail |
| --- | --- | --- |
| Dominant speakers correctly recognized | 3 | 003 / 004 / 001, cross-day similarity 0.900 / 0.949 / 0.914 |
| Misidentification (wrong person) | **0** | blocked by threshold 0.85 |
| Miss (kept generic) | 3 | unregistered acoustically-similar 006 (0.82), small over-segmented clusters |

> **Known limits and the closed loop**: (1) same-gender, genuinely acoustically-similar speakers (two female voices in train_L, CAM++ similarity 0.82) who are unregistered need one naming; (2) over-segmented small clusters from fast turn-taking and very short speakers have unstable centroids and are not forced into a match — they appear as "Speaker N" for you to **name (= register) or merge**, and the library strengthens with each correction. Cross-meeting attribution of action items/decisions is future work.

## 🖥️ Pages

| Page | Route | Description |
|---|---|---|
| Review (home) | `/` | Paste / upload a chat → PII preview → streamed structured report, one-click export |
| Q&amp;A | `/qa/` | Ask questions over the whole conversation; answers cite the original messages |
| Model management | `/models/` | Dual-model recommendation, local status detection, one-click ModelScope download, live switching |
| Batch review | `/batch/` | Process and summarize multiple records in bulk |
| Voice meeting review | `/voice/` | Upload a file or record live; transcription + diarization (rename & proofread); export or distill minutes |
| History | `/history/` | Locally encrypted review history |

## 📸 Screenshots

**① Import a chat** — paste or upload a chat export; encoding and platform format are auto-detected.

<p><img src="docs/images/01_home.png" width="720"></p>

**② Local parsing & PII redaction** — speakers are role-ized as Member A/B; phone / email / names are replaced with placeholders before reaching the model. The mapping stays on-device and is restorable with one click.

<p><img src="docs/images/02_pii.png" width="720"></p>

**③ Structured review report** — four sections: Key Decisions / Action Items (with owner & due date) / Key Information / Risks, with meeting decisions deterministically re-homed.

<p><img src="docs/images/03_report.png" width="500"></p>

**④ Grounded Q&A** — retrieval-augmented over the whole conversation; answers carry verbatim citations, and unmentioned topics are explicitly reported as "not discussed".

<p><img src="docs/images/04_qa.png" width="720"></p>

**⑤ Model management / Batch review / History**

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

## 🚀 Quick Start

**Requirements**: Windows 10/11 (64-bit), Python 3.10–3.12 (3.12 recommended); ~8GB RAM for the 4B model (~4GB for 1.7B);
~3GB disk. Node.js 18+ is only needed if you modify the frontend, not for normal use.

```bash
# 1) Get the code and install dependencies (no torch, no compilation on the default path)
git clone https://gitee.com/FreeBlank/memora.git
cd Memora
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# 2) Environment doctor: checks dependencies / engine / models / disk and suggests fixes
python scripts/doctor.py

# 3) One-click start (doctor -> backend; single-port direct access when the static build exists)
scripts\start.bat
#   Then open http://127.0.0.1:8000
```

**Prepare the inference engine (llama.cpp)**: download a Windows CPU build from the
[llama.cpp official releases](https://github.com/ggml-org/llama.cpp/releases) **dated after 2026-09-07 that includes the
Spark2_5 architecture** (e.g. `llama-b11046-bin-win-cpu-x64.zip`), and extract it into `tools/llamacpp/bin/`;
or set `MEMORA_LLAMASERVER_PATH` to your `llama-server.exe`.

**Prepare the models (network needed during setup)** — either:

- UI: open **Model management**, click **Download** on a recommended card and confirm; the official Q4_K_M GGUF is fetched
  automatically from ModelScope; or
- CLI (first run `set MEMORA_ENFORCE_OFFLINE=0` during setup):

```bash
python scripts/prepare_model.py                                  # default 4B
python scripts/prepare_model.py --model XHToken/Spark-X2.5-1.7B  # lighter 1.7B
```

Equivalent official ModelScope commands (only the single Q4_K_M file is pulled):

```python
from modelscope import snapshot_download
snapshot_download('XHToken/Spark-X2.5-4B-GGUF',   allow_file_pattern=['*Q4_K_M*'])  # ~2.5GB, 8GB+ RAM
snapshot_download('XHToken/Spark-X2.5-1.7B-GGUF', allow_file_pattern=['*Q4_K_M*'])  # ~1.1GB, 4GB+ RAM
snapshot_download('gpustack/bge-m3-GGUF',         allow_file_pattern=['*Q4_K_M*'])  # local RAG embeddings, ~438MB
```

**Prepare the voice pipeline (optional)**:

```bash
conda install ffmpeg                                   # or download an ffmpeg static build into tools/ffmpeg
pip install pywhispercpp speakeronnx onnxruntime       # already included in requirements.txt
# Then open "Voice meeting review" and upload a recording; if the ASR model is missing, download it from hf-mirror when prompted
```

> **Offline guard**: `MEMORA_ENFORCE_OFFLINE=1` by default — the app never goes online; a missing model only raises an error
> with the exact command. Keep the default for an offline demo. You can also download on a connected machine and copy the
> `root/models/models/XHToken--Spark-X2.5-*-GGUF` folder to the same relative location on the target machine.

## 📦 Fully Offline Deployment (to an air-gapped machine)

Run once on a **connected** packaging machine with the same architecture (64-bit Windows + Python 3.10–3.12):

```powershell
# Builds the app + static frontend + local wheelhouse (~70+ wheels incl. binary faiss/numpy)
powershell -ExecutionPolicy Bypass -File scripts/build_offline.ps1
# Add -IncludeModels to also bundle the models (~4GB)
```

The output is `release/Memora/`. Copy the whole folder to a **fully disconnected** Windows machine, then:

```bat
install_offline.bat   :: install dependencies purely offline from the local wheelhouse (pip --no-index)
start.bat             :: start and open http://127.0.0.1:8000
```

**Air-gap acceptance checklist**: `python scripts/doctor.py` all green → physically unplug the network → complete one long-chat
review and one Q&amp;A. The repo ships `scripts/e2e_offline_check.py` (24 end-to-end checks: static hosting, PII redaction &
restoration, SSE streaming, automatic short/long context switching, and zero outbound connections during inference).

## 🏗️ Architecture

The backend is a thin FastAPI layer; all business logic lives in `memora/`. On first inference the default backend launches a
local `llama-server` on a random port (bound to 127.0.0.1 only), speaks the OpenAI-compatible protocol, and terminates the
subprocess on exit / model switch.

```text
Chat export (txt/csv/html)
        │  encoding detection · multi-platform parsing (WeChat/DingTalk/Feishu)
        │
Meeting recording (mp3/m4a/wav…)
        │  ffmpeg decode/denoise·loudness → whisper transcribe → CAM++ speaker diarization
        ▼
   On-device PII redaction (mapping in memory only; restorable)
        │
        ├── short chat ──► full context, zero loss
        └── long chat ───► bge-m3 embeddings + FAISS multi-way recall + timeline skeleton (hard context budget)
        ▼
  llama-server · Spark-X2.5 GGUF (OpenAI-compatible, pure CPU / optional GPU)
        ▼
 Structured report (Decisions/Action items/Risks/Key info + meeting-decision re-homing)
        │            └─ SSE token streaming ─► Next.js frontend
        │               Q&A: same retrieval context + verbatim citations
        ▼
 Fernet-encrypted storage (data/vault) · Markdown / PDF export
```

**Project layout**

```text
Memora/
├── memora/                 # Core business logic (reused by FastAPI)
│   ├── parsers/            #   WeChat / DingTalk / Feishu parsers + encoding detection
│   ├── pii/                #   PII redaction & restoration
│   ├── retrieval/          #   bge-m3 + FAISS local RAG, context budget & timeline skeleton
│   ├── agent/              #   LangChain review / Q&A / voice chains, streaming
│   ├── report/             #   report structuring & meeting-decision re-homing (single source of truth for eval & product)
│   ├── prompts/            #   prompt templates
│   ├── backend/            #   llama-server subprocess backend + optional SGLang backend
│   ├── storage/            #   Fernet local encryption
│   ├── whisper/            #   voice: decode/transcribe/diarization/meeting record
│   ├── model_fetch.py      # model acquisition state machine (official GGUF download + safetensors conversion fallback)
│   ├── exporter.py         # Markdown / PDF export
│   └── batch.py            # batch review
├── server/                 # FastAPI: single port 8000, same-origin hosting of web/out
│   └── routes/             #   review / qa / models / records / export / voice / health
├── web/                    # Next.js + React + Tailwind (app pages + out static build)
├── evals/                  # benchmark, metrics, worker/runner, single-file HTML report
├── samples/                # real WeChat/DingTalk/Feishu parsing samples
├── scripts/                # doctor / prepare_model / start.bat / build_offline.ps1 / e2e
├── tests/                  # 150 pytest cases (no model loading, no network)
├── tools/llamacpp/bin/     # official llama.cpp binaries (download yourself; not in git)
├── requirements.txt        # full dependencies (dev / packaging)
└── requirements-runtime.txt# runtime dependencies (for offline install)
```

## ⚙️ Configuration (`.env` / environment variables)

Copy `.env.example` to `.env` and adjust as needed; every key can be overridden by a same-named environment variable.

| Key | Default | Description |
|---|---|---|
| `MEMORA_MODELS_ROOT` | `../root/models` | Model root (ModelScope cache dir) |
| `MEMORA_MODEL_ID` | 4B | Active model (usually written to `data/settings.json` by the model page) |
| `MEMORA_BACKEND` | `llamacpp` | `llamacpp` (local subprocess) / `sglang` (external GPU server) |
| `MEMORA_ENFORCE_OFFLINE` | `1` | Offline guard: 1 = block all downloads, only raise on a missing model |
| `MEMORA_N_CTX` / `MEMORA_KV_QUANT` | `32768` / `q8_0` | Context window / KV quantization (~3.5GB, 8GB-friendly) |
| `MEMORA_N_GPU` | `0` | GPU offload layers; 0 = all CPU, -1 = all on GPU |
| `MEMORA_RAG_ENABLE` | `1` | Long-chat local RAG; auto-falls back to rule compression without an embedding model |
| `MEMORA_PII_REDACT` | `1` | PII redaction toggle (including speaker name role-ization) |
| `MEMORA_TEMP` / `MEMORA_MAX_REVIEW` / `MEMORA_MAX_QA` | `0.3` / `4096` / `1024` | Decoding temperature & max generation length |
| `MEMORA_ASR_MODEL` / `MEMORA_ASR_VAD` | `ggml-small.bin` / `0` | ASR model tier / built-in VAD (off by default; null model crashes) |
| `MEMORA_SPK_EMBED` / `MEMORA_SPK_SIM` | `campplus-zh-en` / `0.5` | Voiceprint model / AHC clustering threshold (over-segment rather than chain) |
| `MEMORA_CONTACT_THR` | `0.85` | Cross-meeting recognition threshold; lower to 0.75–0.8 near-field on the same device for recall |

## 🧪 Tests & Reproducing the Evaluation

```bash
python -m pytest tests/ -q                          # 150 unit tests: no model loading, no network
# Real-machine offline end-to-end (models required, 24 checks)
set MEMORA_ENFORCE_OFFLINE=1 && python scripts/e2e_offline_check.py
# Full benchmark & ablation (models required, long-running; greedy & reproducible, resumable)
cd evals && python runner.py
# ASR CER/WER and hotword comparison (needs TextGrid ground truth + model)
python scripts/eval_asr.py --textgrid <X.TextGrid> --clip <clip.wav> --t0 30 --t1 210
```

## 🗺️ Roadmap

- [x] Multi-platform parsing, PII redaction, local RAG, SSE streaming, one-click model download, offline package, evaluation & ablation
- [x] Voice meeting pipeline: multi-format transcription, CAM++ speaker diarization, annotated-record export & minutes (scenario-based DER measured)
- [x] Speaker renaming + transcript proofreading; export / minutes use the proofed content (end-to-end verified)
- [x] Live recording & streaming transcription; on stop the whole session is re-transcribed and refined, reusing proofreading / export / minutes (end-to-end verified)
- [x] Cross-session contact voiceprint library: rename = register, automatic recognition in new meetings (dominant speakers zero misidentification cross-day), contact management dialog
- [ ] Cross-meeting attribution of action items/decisions to contacts; semantic disambiguation for acoustically-similar speakers
- [x] ASR CER/WER quantitative evaluation + editable domain hotword list (hotwords cut CER 37.65% to 26.45%)
- [ ] Ship ffmpeg / ASR / voiceprint models in the offline package (currently downloaded via guides)
- [ ] PyInstaller / WebView desktop EXE installer
- [ ] Parsers for more IM / meeting-platform exports
- [ ] Configuration-matrix benchmarks (8GB/16GB, Intel/AMD, with/without GPU)

## 🙏 Acknowledgements & Third-Party Notices

Memora stands on the shoulders of open source. The **copyright of the following third-party open-source components, models
and data always remains with their respective authors / rights holders**. Memora only uses them as dependencies or points you
to their downloads; it **does not claim, transfer or redistribute** any of their rights, and you must keep complying with
their licenses.

**Open-source software dependencies**

| Component | Used for | License |
|---|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | On-device GGUF inference engine (llama-server) | MIT |
| [LangChain](https://github.com/langchain-ai/langchain) / langchain-core / langchain-openai | Agent & chain orchestration | MIT |
| [FastAPI](https://github.com/fastapi/fastapi) / [Uvicorn](https://github.com/encode/uvicorn) | Backend HTTP / ASGI | MIT / BSD-3-Clause |
| [faiss-cpu](https://github.com/facebookresearch/faiss) / [NumPy](https://numpy.org) | Local vector retrieval / numerics | MIT / BSD-3-Clause |
| [pandas](https://pandas.pydata.org) / [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) | Parsing helpers | BSD-3-Clause / MIT |
| [chardet](https://github.com/chardet/chardet) | Encoding detection (dynamically linked as a library, unmodified) | LGPL-2.1-or-later |
| [ModelScope SDK](https://github.com/modelscope/modelscope) | One-click model download | Apache-2.0 |
| [cryptography](https://github.com/pyca/cryptography) | Fernet local encryption | Apache-2.0 OR BSD-3-Clause |
| [python-multipart](https://github.com/Kludex/python-multipart) / [python-dotenv](https://github.com/theskumar/python-dotenv) / [reportlab](https://www.reportlab.com) | Forms / config / PDF export | Apache-2.0 / BSD-3-Clause / BSD-3-Clause |
| [Next.js](https://nextjs.org) / [React](https://react.dev) / [Tailwind CSS](https://tailwindcss.com) | Frontend framework & styling | MIT |
| [pytest](https://github.com/pytest-dev/pytest) | Testing framework | MIT |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) / [pywhispercpp](https://github.com/absadiki/pywhispercpp) | Local speech transcription engine / Python binding | MIT |
| [speakeronnx](https://pypi.org/project/speakeronnx/) / [onnxruntime](https://github.com/microsoft/onnxruntime) | CAM++ speaker voiceprint / ONNX inference | As per official repo / MIT |
| [SciPy](https://scipy.org) / [scikit-learn](https://scikit-learn.org) / [soundfile](https://python-soundfile.readthedocs.io) | Clustering fallback / audio fallback | BSD-3-Clause |
| [ffmpeg](https://ffmpeg.org) | Audio decode / denoise / loudness normalization | LGPL-2.1-or-later or GPL (depends on build; dynamically linked) |

**Models & data (not distributed in this repository)**

| Resource | Rights holder / source | License |
|---|---|---|
| Spark-X2.5-4B / 1.7B (incl. GGUF conversions) | XHToken ([ModelScope](https://modelscope.cn/models/XHToken/Spark-X2.5-4B-GGUF)) | As stated on the official model page |
| bge-m3 (GGUF) | BAAI / gpustack ([ModelScope](https://modelscope.cn/models/gpustack/bge-m3-GGUF)) | As stated on the official model page |
| Whisper ggml ASR models | OpenAI / ggerganov ([HuggingFace](https://huggingface.co/ggerganov/whisper.cpp)) | MIT (weights as officially stated) |
| CAM++ / ERes2Net voiceprint models | ModelScope / speakeronnx (campplus-zh-en) | Apache-2.0 (as per model card) |

> This repository **does not bundle or redistribute** the model weights or llama.cpp binaries; you must obtain them from
> their official sources. License information is subject to each project's official `LICENSE`. If you redistribute Memora,
> you are responsible for simultaneously satisfying the licenses of the referenced components and models.

## 📄 License

The **original source code and documentation** of Memora are released under the permissive [MIT License](LICENSE): you may
freely use, modify, merge, publish, distribute and even use them commercially, provided the copyright and permission notices
are retained in all copies; the software is provided "as is" without any warranty.

- The MIT License **covers only the original code and documentation written by the Memora authors**; it **does not alter or
  override** the licenses of any third-party component or model listed above.
- It is business-friendly and **compatible** with common open-source licenses such as MIT / BSD / Apache / LGPL (dynamic
  linking), so it does not infringe the rights of the referenced open-source projects.
- For any questions about commercial use of the model weights, please refer to the official terms of Spark-X2.5 and bge-m3.

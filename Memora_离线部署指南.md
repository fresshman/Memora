# Memora 离线部署指南（端侧 · 纯本地 · 可断网）

Memora 是端侧离线的对话记录智能复盘工具：本地大模型（Spark-X2.5 4B / 1.7B GGUF）+
本地 bge-m3 向量检索 + FastAPI 后端 + Next.js 静态前端。**全部计算与数据都在本机，
默认强制离线，无任何外网请求、无遥测。**

本指南分两种角色：

- **打包者**（有一次联网机会的机器）：构建静态前端、下载离线依赖，产出可分发的发布包；
- **使用者**（完全断网的机器）：解压、离线装依赖、放模型、一键启动。

---

## 一、架构与端口

| 组件 | 技术 | 说明 |
| --- | --- | --- |
| 推理引擎 | llama.cpp `llama-server`（随包 `tools/llamacpp`） | 加载 GGUF，提供本地 OpenAI 兼容接口；embedding 复用同一引擎 |
| 对话模型 | Spark-X2.5-4B（主力）/ 1.7B（轻量） | ModelScope：`XHToken/Spark-X2.5-4B-GGUF`、`XHToken/Spark-X2.5-1.7B-GGUF` |
| 向量模型 | bge-m3 Q4_K_M GGUF（约 438MB） | `gpustack/bge-m3-GGUF`，超长对话 RAG 检索 |
| 后端 | FastAPI + LangChain | 单进程，`http://127.0.0.1:8000` |
| 前端 | Next.js **静态导出**（`web/out`） | 由后端**单端口同源托管**，使用者机器**无需 Node.js** |

构建出静态前端后，**只有一个端口 8000**：浏览器访问 `http://127.0.0.1:8000`
即同时拿到页面与 `/api` 接口。开发模式（`npm run dev`，端口 3000）仅开发者需要。

---

## 二、打包者：在有网机器上生成离线发布包

前置：64 位 Windows、Python 3.10–3.12、Node.js 18+（仅打包机构建前端需要）。

```powershell
# 在项目根目录 Memora\ 下
powershell -ExecutionPolicy Bypass -File scripts\build_offline.ps1
# 若要把约 4GB 模型也打进发布包（可彻底免下载）：
powershell -ExecutionPolicy Bypass -File scripts\build_offline.ps1 -IncludeModels
```

脚本依次完成：

1. `cd web; npm ci; npm run build` —— 静态导出到 `web/out`（API 基址编译为同源相对路径）；
2. `pip download -r requirements.txt -d wheelhouse` —— 下载全部 Python 依赖的
   Windows 离线 wheel（含 faiss-cpu、numpy、cryptography 等）；
3. 组装 `release\Memora\`：应用代码、静态前端、样本、llama.cpp 引擎、测试、
   `wheelhouse`、`requirements.txt`、`install_offline.bat`、根目录 `start.bat`；
4. 模型默认不打入（体积大），加 `-IncludeModels` 才复制到 `release\root\models`。

> 平台一致性：faiss-cpu / numpy 等含二进制 wheel，**打包机与目标机需同为 64 位
> Windows、Python 小版本尽量一致（3.12 对 3.12）**。

把整个 `release\` 目录拷贝到 U 盘 / 内网即可分发。

---

## 三、使用者：在断网机器上安装与启动

1. **解压发布包**，进入 `Memora\` 目录。
2. **（可选）创建虚拟环境**：
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. **离线安装依赖**：双击 `install_offline.bat`
   （等价于 `pip install --no-index --find-links=wheelhouse -r requirements.txt`，全程不联网）。
4. **放置模型**（二选一）：
   - 发布包已含模型（`-IncludeModels`）：无需操作；
   - 否则在**有网时**先启动一次，进入「模型管理」页，对推荐的
     **Spark-X2.5-4B / Spark-X2.5-1.7B** 点下载（默认走 ModelScope，自动落盘即用）；
     也可手动把模型目录放到项目上一级 `root\models\`，布局为
     `root\models\<组织>--<仓库名>\snapshots\master\<.gguf>`。
     推荐同时具备 bge-m3 向量模型以启用超长对话 RAG（缺失会自动降级为规则压缩）。
5. **一键启动**：双击 `start.bat`（或 `scripts\start.bat`）。
   脚本先做环境自检 `scripts\doctor.py`，随后启动后端并自动打开浏览器：
   - 检测到 `web/out`：单端口 `http://127.0.0.1:8000`；
   - 未构建前端：回退开发模式（需要 Node，端口 3000）。

---

## 四、断网验收清单（演示前逐项打勾）

> 建议在系统层面断开 Wi-Fi / 拔网线后执行，验证全程无网络依赖。

1. `python scripts\doctor.py`：模型、faiss、bge、PII 脱敏等项为 `[OK]`/`[WARN]`，无必须修复的 `[FAIL]`。
2. 启动后浏览器打开 `http://127.0.0.1:8000`，页面正常加载（静态前端同源托管）。
3. 「模型管理」页能识别本地 4B / 1.7B，状态为就绪；切换模型无需联网。
4. 导入一段含手机号 / 邮箱 / 身份证 / 发言人真名的对话：
   - 导入后出现绿色「已在本地脱敏：手机 N、邮箱 N、人名 N…」提示；
   - 对话预览中敏感信息已变为 `【手机1】`、发言人变为 `成员A/成员B`；
   - 生成报告后点「还原真实信息」，仅在本机还原当前视图。
5. 短对话「一键全局复盘」：流式逐字输出（SSE），标题旁显示「全量上下文」。
6. 超长对话（>2 万字）：标题旁显示「RAG 检索增强」，待办 / 风险 / 决定
   跨开头、中段、结尾均不遗漏（评测集召回 100%）。
7. 「对话问答」页：流式回答、有证据引用；对无答案问题不乱编（幻觉率 0）。
8. 「加密保存」：报告以 Fernet 加密写入 `data\vault`，「一键清空」后不可恢复。
9. 全程用资源监视器 / 防火墙确认：除 `127.0.0.1` 本地回环外**无任何外联连接**。

---

## 五、常用配置（环境变量，可写入 `.env` 或 `scripts\run_env.bat`）

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `MEMORA_ENFORCE_OFFLINE` | `1` | 离线红线，置 `1` 时模型缺失绝不联网，并同步设置 HF/ModelScope 离线标志 |
| `MEMORA_MODEL_ID` | 自动 | 直接指定使用的模型仓库 id |
| `MEMORA_PII_REDACT` | `1` | PII 脱敏总开关 |
| `MEMORA_PII_REDACT_NAMES` | `1` | 人名角色化开关，置 `0` 只脱敏号码/证件 |
| `MEMORA_RAG_ENABLE` | `1` | 超长对话本地向量检索开关 |
| `MEMORA_RAG_TRIGGER_CHARS` | 输入截断字数 | 超过该字数启用 RAG |
| `MEMORA_N_CTX` | `32768` | llama-server 上下文长度 |
| `MEMORA_N_GPU` | `0` | 卸载到 GPU 的层数（纯 CPU 保持 0） |
| `MEMORA_TEMP` | `0.3` | 采样温度（评测时用 `0` 贪心解码保证可复现） |
| `NEXT_PUBLIC_API_BASE` | 空（同源） | 仅开发模式需要，指向 `http://127.0.0.1:8000` |

完整变量见 `.env.example`。

---

## 六、故障排查

- **端口 8000 被占用**：`netstat -ano | findstr :8000` 找到进程关闭，或改启动命令端口。
- **8GB 内存吃紧**：优先用 1.7B 模型；`MEMORA_KV_QUANT=q8_0`、`MEMORA_N_GPU=0`；
  关闭其他大内存程序。首次加载模型较慢属正常。
- **页面能开但接口报错 / 模型未就绪**：看后端窗口日志与 `data\logs\memora.log`，
  运行 `doctor.py` 确认 GGUF 文件与 llama-server 路径。
- **超长对话变慢**：RAG 已把送入模型的上下文收敛到约 7600 字 / 20 块；
  缺 bge 模型会降级为规则压缩（覆盖各话题段但精度略低），建议补装 bge-m3。
- **离线安装 wheel 失败**：多为打包机与目标机 Python 版本 / 架构不一致，
  请在同版本 64 位 Python 的有网机器重新 `build_offline.ps1`。
- **前端开发**：开发者在 `web\` 下 `npm run dev`（端口 3000），依赖 `web\.env.local`
  把 API 指向 8000；发布给最终用户用静态导出，不需要 Node。

import { createFileRoute } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Cpu,
  Download,
  FileText,
  Github,
  ListTodo,
  Lock,
  MessagesSquare,
  Mic,
  PlayCircle,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  WifiOff,
  Zap,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  component: Index,
});

/* ------------------------------------------------------------------ */
/* 数据                                                                */
/* ------------------------------------------------------------------ */

const PAIN_POINTS: ReadonlyArray<{
  icon: LucideIcon;
  title: string;
  desc: string;
}> = [
  {
    icon: Lock,
    title: "隐私顾虑",
    desc: "微信、钉钉、客户沟通记录属于高敏感内容，不敢上传任何第三方云端 AI 平台。",
  },
  {
    icon: MessagesSquare,
    title: "信息海量",
    desc: "单次对话动辄数万字、群聊数百条，人工翻阅提炼要点耗时巨大。",
  },
  {
    icon: Search,
    title: "工具能力不足",
    desc: "传统工具只能关键词检索，无法跨话题、跨时间关联上下文，纪要能力弱。",
  },
];

const FEATURES: ReadonlyArray<{
  icon: LucideIcon;
  title: string;
  desc: string;
}> = [
  {
    icon: FileText,
    title: "多格式对话导入",
    desc: "支持微信 / 钉钉 / 飞书导出的 TXT、CSV、HTML，自动识别发言人、时间、内容，还原完整时序。",
  },
  {
    icon: Sparkles,
    title: "一键全局智能复盘",
    desc: "基于完整对话上下文输出结构化报告：核心结论、待办清单、关键信息、风险提示。",
  },
  {
    icon: Search,
    title: "对话智能问答",
    desc: "自然语言提问，基于全部聊天记录精准检索历史沟通信息，不再翻聊天记录。",
  },
  {
    icon: Mic,
    title: "本地语音复盘",
    desc: "集成本地离线 Whisper 转写，导入会议录音 / 语音文件，自动转写并生成纪要。",
  },
  {
    icon: ShieldCheck,
    title: "本地加密存储",
    desc: "所有导入记录与产出在本地加密保存，支持一键清空，无后台上传、无用户采集。",
  },
  {
    icon: WifiOff,
    title: "100% 离线运行",
    desc: "文本解析、AI 总结、语音转写、问答检索全部本地完成，断网也能复盘。",
  },
];

const HIGHLIGHTS: ReadonlyArray<{
  icon: LucideIcon;
  title: string;
  desc: string;
}> = [
  {
    icon: Cpu,
    title: "1M 超长上下文",
    desc: "一次性完整载入数万至几十万字对话，全局理解因果关系，效果优于分片 RAG。",
  },
  {
    icon: Lock,
    title: "隐私绝对安全",
    desc: "数据 100% 保留在本机，架构层面杜绝外泄，从底层解决“不敢上传 AI”。",
  },
  {
    icon: Zap,
    title: "低设备门槛",
    desc: "无需高端显卡，普通 8G 内存 PC 即可流畅运行，本地低时延推理。",
  },
];

const STATS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "1M", label: "超长上下文窗口" },
  { value: "≈2.9GB", label: "整机峰值内存占用" },
  { value: "≤12s", label: "10 万字全量分析" },
  { value: "0", label: "网络请求 / 数据上传" },
];

/* ------------------------------------------------------------------ */
/* 区块                                                                */
/* ------------------------------------------------------------------ */

function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 text-white">
            <Sparkles className="size-4" />
          </div>
          <span className="text-lg font-bold tracking-tight text-slate-900">
            Memora
          </span>
          <Badge variant="secondary" className="ml-1 hidden sm:inline-flex">
            端侧离线 AI
          </Badge>
        </div>
        <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
          <a href="#video" className="transition-colors hover:text-slate-900">
            演示视频
          </a>
          <a href="#pain" className="transition-colors hover:text-slate-900">
            痛点
          </a>
          <a href="#features" className="transition-colors hover:text-slate-900">
            功能
          </a>
          <a href="#why" className="transition-colors hover:text-slate-900">
            为什么
          </a>
        </nav>
        <Button asChild size="sm">
          <a href="#video">观看演示</a>
        </Button>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white">
      <div className="absolute -top-24 left-1/2 -z-10 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-gradient-to-r from-indigo-400/30 to-violet-400/30 blur-3xl" />
      <div className="mx-auto max-w-5xl px-5 pb-16 pt-20 text-center">
        <Badge className="mb-5 bg-indigo-600 text-white hover:bg-indigo-600">
          离线 · 私密 · 对话智能复盘
        </Badge>
        <h1 className="text-balance text-4xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-6xl">
          把你的聊天记录，
          <br />
          变成一份<span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">结构化智能纪要</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-slate-600">
          Memora 是一款 100% 离线运行的 Windows 桌面端 AI 工具。基于 Spark-X2.5-4B
          的 1M 超长上下文，一次性全局理解你的完整对话，自动提炼结论、待办与风险——
          数据全程不出本机。
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg" className="bg-indigo-600 hover:bg-indigo-700">
            <a href="#video">
              <PlayCircle className="size-4" />
              观看演示视频
            </a>
          </Button>
          <Button asChild size="lg" variant="outline">
            <a href="#features">
              <Sparkles className="size-4" />
              了解核心功能
            </a>
          </Button>
          <Button
            asChild
            size="lg"
            variant="ghost"
            className="text-slate-600 hover:text-slate-900"
          >
            <a
              href="https://gitee.com/FreeBlank/memora"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Github className="size-4" />
              源码仓库 (Gitee)
            </a>
          </Button>
        </div>

        <dl className="mx-auto mt-14 grid max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4">
          {STATS.map((s) => (
            <div
              key={s.label}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <dt className="text-2xl font-bold text-slate-900">{s.value}</dt>
              <dd className="mt-1 text-xs leading-snug text-slate-500">
                {s.label}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

function VideoShowcase() {
  return (
    <section id="video" className="border-y border-slate-100 bg-white py-20">
      <div className="mx-auto max-w-4xl px-5">
        <div className="mb-10 text-center">
          <Badge variant="secondary" className="mb-3">
            产品演示
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            60 秒看懂 Memora 怎么用
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-slate-600">
            断网环境下导入对话、一键复盘、智能问答——全程本地完成。
          </p>
        </div>
        <div className="relative">
          <div className="absolute -inset-3 rounded-3xl bg-gradient-to-r from-indigo-500/20 to-violet-500/20 blur-2xl" />
          <video
            className="relative aspect-video w-full rounded-2xl border border-slate-200 bg-black shadow-2xl"
            src="/assets/memora-intro.mp4"
            controls
            preload="metadata"
            playsInline
          >
            您的浏览器不支持内嵌视频，请下载 memora-intro.mp4 查看演示。
          </video>
        </div>
        <p className="mt-4 text-center text-sm text-slate-500">
          演示视频为本地录制，无任何云端服务参与。
        </p>
      </div>
    </section>
  );
}

function PainPoints() {
  return (
    <section id="pain" className="bg-slate-50 py-20">
      <div className="mx-auto max-w-6xl px-5">
        <div className="mb-12 text-center">
          <Badge variant="secondary" className="mb-3">
            用户痛点
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            谁在用，又卡在哪
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-600">
            职场人群、销售、学生社团，以及任何重视隐私的普通用户——在整理沟通记录时反复遇到这三道坎。
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {PAIN_POINTS.map((p) => (
            <Card key={p.title} className="border-slate-200">
              <CardHeader>
                <div className="mb-2 flex size-11 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                  <p.icon className="size-5" />
                </div>
                <CardTitle className="text-lg">{p.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                  {p.desc}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="bg-white py-20">
      <div className="mx-auto max-w-6xl px-5">
        <div className="mb-12 text-center">
          <Badge variant="secondary" className="mb-3">
            核心功能
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            从导入到纪要，一条链路闭环
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-600">
            全部功能 100% 离线本地运行，覆盖文字沟通与语音会议两类场景。
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <Card
              key={f.title}
              className="border-slate-200 transition-shadow hover:shadow-md"
            >
              <CardHeader>
                <div className="mb-2 flex size-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <f.icon className="size-5" />
                </div>
                <CardTitle className="text-lg">{f.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                  {f.desc}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhySection() {
  return (
    <section id="why" className="bg-gradient-to-b from-slate-900 to-slate-800 py-20 text-white">
      <div className="mx-auto max-w-6xl px-5">
        <div className="mb-12 text-center">
          <Badge className="mb-3 bg-white/10 text-white hover:bg-white/10">
            端侧核心价值
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight">
            为什么必须是端侧离线
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-300">
            聊天记录是高隐私数据，云端方案天然受限。Memora 用本地推理从底层化解这一矛盾。
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {HIGHLIGHTS.map((h) => (
            <div
              key={h.title}
              className="rounded-2xl border border-white/10 bg-white/5 p-6"
            >
              <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500">
                <h.icon className="size-5" />
              </div>
              <h3 className="text-lg font-semibold">{h.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">
                {h.desc}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center gap-4 rounded-2xl border border-white/10 bg-white/5 p-8 text-center">
          <AlertTriangle className="size-8 text-amber-400" />
          <p className="max-w-2xl text-slate-200">
            <span className="font-semibold text-white">隐私红线：</span>
            本应用任何模块都不会发起对外网络请求。所有导入记录与生成结果仅保存在你的本机，无后台上传、无用户数据采集。
          </p>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-slate-900 py-10 text-slate-400">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-5 text-center">
        <div className="flex items-center gap-2 text-slate-200">
          <Sparkles className="size-4 text-indigo-400" />
          <span className="font-semibold">Memora</span>
        </div>
        <p className="text-sm">
          基于 Spark-X2.5-4B 端侧超长上下文 AI 的离线私密对话智能复盘工具
        </p>
        <p className="text-xs text-slate-500">
          © {new Date().getFullYear()} Memora · 数据 100% 本地 · 全程离线运行
        </p>
        <a
          href="https://gitee.com/FreeBlank/memora"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-indigo-400 transition-colors hover:text-indigo-300"
        >
          <Github className="size-4" />
          开源仓库：gitee.com/FreeBlank/memora
        </a>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/* 页面                                                                */
/* ------------------------------------------------------------------ */

function Index() {
  return (
    <div className="min-h-screen bg-white font-sans text-slate-900">
      <Nav />
      <Hero />
      <VideoShowcase />
      <PainPoints />
      <Features />
      <WhySection />
      <Footer />
    </div>
  );
}

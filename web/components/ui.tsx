"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { IconLoader } from "./icons";

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

/* ================= Button ================= */
type Variant = "primary" | "dark" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary:
    "text-white bg-gradient-to-b from-brand-500 to-brand-700 border border-brand-700/40 hover:from-brand-400 hover:to-brand-600 shadow-glow",
  dark: "text-white bg-slate-900 border border-slate-900 hover:bg-slate-800",
  secondary:
    "bg-slate-100 text-slate-700 border border-transparent hover:bg-slate-200",
  outline:
    "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300",
  ghost: "text-slate-600 border border-transparent hover:bg-slate-100",
  danger: "text-white bg-red-600 border border-red-600 hover:bg-red-500",
};
const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs rounded-lg gap-1.5",
  md: "h-9.5 px-4 text-sm rounded-xl gap-2 py-2",
  lg: "h-12 px-6 text-sm rounded-xl gap-2",
};

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...rest
}: BtnProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-medium whitespace-nowrap",
        "transition-all duration-150 select-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40",
        "disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <IconLoader className="w-4 h-4" /> : icon}
      {children}
    </button>
  );
}

/* ================= Badge ================= */
type Tone = "brand" | "slate" | "green" | "amber" | "red" | "blue";
const TONES: Record<Tone, string> = {
  brand: "bg-brand-50 text-brand-700 border-brand-200",
  slate: "bg-slate-100 text-slate-600 border-slate-200",
  green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red: "bg-red-50 text-red-700 border-red-200",
  blue: "bg-sky-50 text-sky-700 border-sky-200",
};

export function Badge({
  tone = "slate",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ================= Status dot ================= */
const DOT: Record<Tone, string> = {
  brand: "bg-brand-500",
  slate: "bg-slate-400",
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
  blue: "bg-sky-500",
};
export function StatusDot({
  tone = "green",
  pulse = false,
}: {
  tone?: Tone;
  pulse?: boolean;
}) {
  return (
    <span className="relative inline-flex w-2 h-2">
      {pulse && (
        <span
          className={cn(
            "absolute inline-flex w-full h-full rounded-full opacity-60 animate-ping",
            DOT[tone],
          )}
        />
      )}
      <span className={cn("relative inline-flex w-2 h-2 rounded-full", DOT[tone])} />
    </span>
  );
}

/* ================= Progress ================= */
export function Progress({
  value,
  tone = "brand",
  className,
}: {
  value?: number;
  tone?: Tone;
  className?: string;
}) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-slate-200", className)}>
      {value === undefined ? (
        <div
          className="h-full w-1/3 rounded-full bg-brand-500"
          style={{ animation: "indeterminate 1.2s ease-in-out infinite" }}
        />
      ) : (
        <div
          className={cn("h-full rounded-full transition-all duration-300", DOT[tone])}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      )}
    </div>
  );
}

/* ================= Page header ================= */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-7 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ================= Step title ================= */
export function StepTitle({
  n,
  title,
  meta,
}: {
  n: number | string;
  title: string;
  meta?: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
        {n}
      </span>
      <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      {meta && <span className="text-xs text-slate-400">· {meta}</span>}
    </div>
  );
}

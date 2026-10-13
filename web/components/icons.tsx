import type { SVGProps, ReactNode } from "react";

type P = SVGProps<SVGSVGElement>;

function Base({ children, ...p }: P & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...p}
    >
      {children}
    </svg>
  );
}

/* ===== 品牌 Logo（字母 M） ===== */
export const LogoM = (p: P) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...p}>
    <path d="M5 18V6l7 7 7-7v12" />
  </svg>
);

/* ===== 导航 ===== */
export const IconReview = (p: P) => (
  <Base {...p}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    <path d="M8 8h8M8 11h5" />
  </Base>
);
export const IconLayers = (p: P) => (
  <Base {...p}>
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </Base>
);
export const IconQA = (p: P) => (
  <Base {...p}>
    <path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2z" />
    <path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1" />
  </Base>
);
export const IconMic = (p: P) => (
  <Base {...p}>
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 10a7 7 0 0 0 14 0" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </Base>
);
export const IconHistory = (p: P) => (
  <Base {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
    <path d="M12 7v5l3 2" />
  </Base>
);
export const IconCpu = (p: P) => (
  <Base {...p}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <rect x="9" y="9" width="6" height="6" />
    <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
  </Base>
);

/* ===== 通用 ===== */
export const IconUpload = (p: P) => (
  <Base {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </Base>
);
export const IconClipboard = (p: P) => (
  <Base {...p}>
    <rect x="8" y="2" width="8" height="4" rx="1" />
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
  </Base>
);
export const IconShield = (p: P) => (
  <Base {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="m9 12 2 2 4-4" />
  </Base>
);
export const IconSparkles = (p: P) => (
  <Base {...p}>
    <path d="M12 3l1.9 4.6L18.5 9.5 13.9 11.4 12 16l-1.9-4.6L5.5 9.5l4.6-1.9z" />
    <path d="M19 14l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
  </Base>
);
export const IconCheck = (p: P) => (
  <Base {...p}><polyline points="20 6 9 17 4 12" /></Base>
);
export const IconCheckCircle = (p: P) => (
  <Base {...p}>
    <path d="M22 11.1V12a10 10 0 1 1-5.9-9.1" />
    <polyline points="22 4 12 14 9 11" />
  </Base>
);
export const IconAlert = (p: P) => (
  <Base {...p}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </Base>
);
export const IconInfo = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </Base>
);
export const IconDownload = (p: P) => (
  <Base {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </Base>
);
export const IconChevronRight = (p: P) => (
  <Base {...p}><polyline points="9 18 15 12 9 6" /></Base>
);
export const IconChevronDown = (p: P) => (
  <Base {...p}><polyline points="6 9 12 15 18 9" /></Base>
);
export const IconLock = (p: P) => (
  <Base {...p}>
    <rect x="3" y="11" width="18" height="11" rx="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </Base>
);
export const IconFileDown = (p: P) => (
  <Base {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <path d="M12 18v-6M9 15l3 3 3-3" />
  </Base>
);
export const IconRefresh = (p: P) => (
  <Base {...p}>
    <polyline points="23 4 23 10 17 10" />
    <path d="M20.5 15a9 9 0 1 1-2.1-9.4L23 10" />
  </Base>
);
export const IconLoader = (p: P) => (
  <Base {...p} className={`animate-spin ${p.className ?? ""}`}>
    <path d="M21 12a9 9 0 1 1-6.2-8.6" />
  </Base>
);
export const IconX = (p: P) => (
  <Base {...p}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </Base>
);
export const IconCalendar = (p: P) => (
  <Base {...p}>
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </Base>
);
export const IconPin = (p: P) => (
  <Base {...p}>
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
    <circle cx="12" cy="10" r="3" />
  </Base>
);
export const IconMail = (p: P) => (
  <Base {...p}>
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <polyline points="22,6 12,13 2,6" />
  </Base>
);
export const IconPhone = (p: P) => (
  <Base {...p}>
    <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.2 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z" />
  </Base>
);
export const IconSend = (p: P) => (
  <Base {...p}>
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </Base>
);
export const IconTodo = (p: P) => (
  <Base {...p}>
    <path d="m3 17 2 2 4-4" />
    <path d="m3 7 2 2 4-4" />
    <path d="M13 6h8M13 12h8M13 18h8" />
  </Base>
);
export const IconKey = (p: P) => (
  <Base {...p}>
    <path d="M2 18v3h3" />
    <path d="M21 2l-9.6 9.6" />
    <circle cx="7.5" cy="15.5" r="4.5" />
  </Base>
);
export const IconBulb = (p: P) => (
  <Base {...p}>
    <path d="M9 18h6M10 22h4" />
    <path d="M15.1 14a6 6 0 1 0-6.2 0c.6.7 1.1 1.3 1.1 2.5V18h4v-1.5c0-1.2.5-1.8 1.1-2.5z" />
  </Base>
);
export const IconFile = (p: P) => (
  <Base {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
  </Base>
);
export const IconSearch = (p: P) => (
  <Base {...p}>
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.7" y2="16.7" />
  </Base>
);
export const IconUsers = (p: P) => (
  <Base {...p}>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
  </Base>
);
export const IconDatabase = (p: P) => (
  <Base {...p}>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 5v6c0 1.7-4 3-9 3s-9-1.3-9-3V5" />
    <path d="M21 11v6c0 1.7-4 3-9 3s-9-1.3-9-3v-6" />
  </Base>
);
export const IconTrash = (p: P) => (
  <Base {...p}>
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <line x1="10" y1="11" x2="10" y2="17" />
    <line x1="14" y1="11" x2="14" y2="17" />
  </Base>
);
export const IconEye = (p: P) => (
  <Base {...p}>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </Base>
);
export const IconZap = (p: P) => (
  <Base {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></Base>
);
export const IconArrowRight = (p: P) => (
  <Base {...p}>
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </Base>
);
export const IconSave = (p: P) => (
  <Base {...p}>
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </Base>
);
export const IconClock = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </Base>
);
export const IconPencil = (p: P) => (
  <Base {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </Base>
);
export const IconUndo = (p: P) => (
  <Base {...p}>
    <path d="M3 7v6h6" />
    <path d="M3 13a9 9 0 1 0 3-7.7L3 8" />
  </Base>
);
export const IconPackage = (p: P) => (
  <Base {...p}>
    <path d="M16.5 9.4 7.5 4.21" />
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />
  </Base>
);
export const IconBrain = (p: P) => (
  <Base {...p}>
    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
    <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
  </Base>
);

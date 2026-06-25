"use client";

import type { AsyncState } from "@/lib/portalTypes";
import { useI18n } from "@/lib/i18n";

const STR = {
  en: {
    loading: "Loading",
    dismiss: "Dismiss",
    errorLabel: "Couldn't load this.",
    retryLabel: "Retry",
  },
  vi: {
    loading: "Đang tải",
    dismiss: "Đóng",
    errorLabel: "Không thể tải nội dung này.",
    retryLabel: "Thử lại",
  },
} as const;

// ---- Page header ------------------------------------------------------------
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h2 className="page-title">{title}</h2>
        {description && <p className="page-desc">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

// ---- Section header (within a page) ----------------------------------------
export function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-header">
      <h3 className="section-title">{title}</h3>
      {action}
    </div>
  );
}

// ---- Card -------------------------------------------------------------------
export function Card({
  children,
  className = "",
  style,
  as: As = "div",
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  as?: "div" | "section";
}) {
  return (
    <As className={`card ${className}`} style={style}>
      {children}
    </As>
  );
}

// ---- Stat card --------------------------------------------------------------
export function StatCard({
  label,
  value,
  hint,
  tone = "default",
  icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "default" | "success" | "warning" | "danger" | "gold";
  icon?: React.ReactNode;
}) {
  return (
    <div className={`stat-card tone-${tone}`}>
      {icon && <span className="stat-icon">{icon}</span>}
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

// ---- Badge ------------------------------------------------------------------
export type BadgeTone =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "info"
  | "gold";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

// ---- Empty state ------------------------------------------------------------
export function EmptyState({
  icon,
  title,
  description,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
}) {
  return (
    <div className="empty-state">
      {icon && <span className="empty-icon">{icon}</span>}
      <p className="empty-title">{title}</p>
      {description && <p className="empty-desc">{description}</p>}
    </div>
  );
}

// ---- Async boundary ---------------------------------------------------------
// Renders loading skeleton rows / an error card with retry / or the children for the
// resolved data. Keeps every API-backed view consistent.
export function AsyncBoundary<T>({
  state,
  onRetry,
  children,
  rows = 3,
  errorLabel,
  retryLabel,
}: {
  state: AsyncState<T>;
  onRetry?: () => void;
  children: (data: T) => React.ReactNode;
  rows?: number;
  errorLabel?: string;
  retryLabel?: string;
}) {
  const { lang } = useI18n();
  const s = STR[lang];
  const resolvedErrorLabel = errorLabel ?? s.errorLabel;
  const resolvedRetryLabel = retryLabel ?? s.retryLabel;
  if (state.status === "loading") {
    return (
      <div className="skeleton-stack" aria-busy="true" aria-label={s.loading}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="skeleton-card">
            <div className="skel-line w-40" />
            <div className="skel-line w-90" />
            <div className="skel-line w-70" />
          </div>
        ))}
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="load-error" role="alert">
        <p>{resolvedErrorLabel}</p>
        <p className="load-error-detail">{state.error}</p>
        {onRetry && (
          <button className="btn btn-outline" onClick={onRetry}>
            {resolvedRetryLabel}
          </button>
        )}
      </div>
    );
  }
  return <>{children(state.data)}</>;
}

// ---- Toast (lightweight, self-dismissing) ----------------------------------
export function Toast({
  message,
  tone = "success",
  onClose,
}: {
  message: string;
  tone?: "success" | "info" | "danger";
  onClose: () => void;
}) {
  const { lang } = useI18n();
  const s = STR[lang];
  return (
    <div className={`toast toast-${tone}`} role="status">
      <span>{message}</span>
      <button className="toast-close" onClick={onClose} aria-label={s.dismiss}>
        ✕
      </button>
    </div>
  );
}

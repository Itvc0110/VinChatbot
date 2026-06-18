// Small presentational helpers shared across portal screens. Pure, no React.

// VND amounts are large — format with thin separators and a ₫ suffix (VN convention).
export function formatVnd(amount: number): string {
  return `${amount.toLocaleString("vi-VN")} ₫`;
}

// Compact VND for tight stat cards: 80,000,000 -> "₫80M".
export function formatVndCompact(amount: number): string {
  if (amount >= 1_000_000) return `₫${(amount / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 1 })}M`;
  if (amount >= 1_000) return `₫${Math.round(amount / 1_000)}K`;
  return `₫${amount}`;
}

const MS_PER_DAY = 86_400_000;

// Whole days from now until the ISO datetime (negative = past). Uses calendar-day
// boundaries so "due tonight" and "due this morning" both read as today (0).
export function daysUntil(iso: string, now: Date = new Date()): number {
  const target = new Date(iso);
  const a = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate());
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((a - b) / MS_PER_DAY);
}

export function formatDate(iso: string, locale = "en-US"): string {
  return new Date(iso).toLocaleDateString(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(iso: string, locale = "en-US"): string {
  return new Date(iso).toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// "2 days ago" / "in 3 days" / "today" — for last-crawled, last-updated chips.
export function relativeTime(iso: string, now: Date = new Date()): string {
  const diff = new Date(iso).getTime() - now.getTime();
  const days = Math.round(diff / MS_PER_DAY);
  if (days === 0) {
    const hours = Math.round(diff / 3_600_000);
    if (hours === 0) return "just now";
    return hours < 0 ? `${-hours}h ago` : `in ${hours}h`;
  }
  if (days < 0) return `${-days}d ago`;
  return `in ${days}d`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

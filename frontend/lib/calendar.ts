// Pure date helpers for the calendar grid. Week starts on Monday (VinUni convention).
// No React — safe to import anywhere.

export function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

// Monday of the week containing `d`.
export function startOfWeek(d: Date): Date {
  const x = startOfDay(d);
  const dow = (x.getDay() + 6) % 7; // 0 = Monday … 6 = Sunday
  return addDays(x, -dow);
}

export function endOfWeek(d: Date): Date {
  return addDays(startOfWeek(d), 6);
}

export function weekDays(d: Date): Date[] {
  const s = startOfWeek(d);
  return Array.from({ length: 7 }, (_, i) => addDays(s, i));
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

// 6×7 grid of dates covering the month of `d` (leading/trailing days from adjacent months).
export function monthMatrix(d: Date): Date[][] {
  let cur = startOfWeek(startOfMonth(d));
  const weeks: Date[][] = [];
  for (let w = 0; w < 6; w++) {
    const row: Date[] = [];
    for (let i = 0; i < 7; i++) {
      row.push(cur);
      cur = addDays(cur, 1);
    }
    weeks.push(row);
  }
  return weeks;
}

export function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function isToday(d: Date): boolean {
  return sameDay(d, new Date());
}

export function isSameMonth(d: Date, ref: Date): boolean {
  return d.getMonth() === ref.getMonth() && d.getFullYear() === ref.getFullYear();
}

// Stable day key for grouping events by date.
export function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
}

export function monthTitle(d: Date, locale: string): string {
  return d.toLocaleDateString(locale, { month: "long", year: "numeric" });
}

export function weekTitle(d: Date, locale: string): string {
  const s = startOfWeek(d);
  const e = endOfWeek(d);
  const sStr = s.toLocaleDateString(locale, { month: "short", day: "numeric" });
  const eStr = e.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" });
  return `${sStr} – ${eStr}`;
}

export function timeLabel(iso: string, locale: string): string {
  return new Date(iso).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

// Localized short weekday labels Mon…Sun (derived from any real week).
export function weekdayLabels(locale: string): string[] {
  return weekDays(new Date()).map((d) =>
    d.toLocaleDateString(locale, { weekday: "short" })
  );
}

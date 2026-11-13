export function formatScore(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function formatSigned(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function formatHours(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number.isInteger(value) ? value : value.toFixed(1)} h`;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-US");
}

export function humanize(code: string): string {
  return code.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Parse an optional numeric form value; empty -> null. */
export function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/** Split a '|'-separated annotation ("a|b") into distinct trimmed labels. */
export function splitLabels(value: unknown): string[] {
  if (typeof value !== "string") return [];
  return [...new Set(value.split("|").map((part) => part.trim()).filter(Boolean))];
}

/** Express a 0-100 percentile as how exclusive it is: 98.8 -> "Top 1.2%". */
export function topPercent(percentile: number | null | undefined): string {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) return "—";
  const top = Math.max(0, 100 - percentile);
  if (top < 0.1) return "Top 0.1%";
  return `Top ${top < 10 ? top.toFixed(1) : Math.round(top)}%`;
}

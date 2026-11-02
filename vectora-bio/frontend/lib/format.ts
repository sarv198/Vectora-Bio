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

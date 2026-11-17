"use client";

import { ChevronDown, Info, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  KeyboardEvent,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

/* ---------------------------------------------------------------------------------------
 * Page structure
 * ------------------------------------------------------------------------------------- */

export function PageHeader({
  title,
  description,
  actions,
  context,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  /** Location in the app, e.g. "Analysis". */
  context?: string;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {context && <p className="mb-1 text-[12.5px] text-ink-3">{context}</p>}
        <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.01em] text-ink">{title}</h1>
        {description && <p className="mt-1.5 max-w-[68ch] text-[13.5px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A titled region of a page. No box: hierarchy comes from the heading and spacing. */
export function Section({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`min-w-0 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-3 text-[12.5px] text-ink-3">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** The one bordered container: used for the query area and similar working surfaces. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-line bg-surface ${className}`}>{children}</div>;
}

export function Divider({ className = "" }: { className?: string }) {
  return <hr className={`border-0 border-t border-line ${className}`} />;
}

/* ---------------------------------------------------------------------------------------
 * Numbers and evidence
 * ------------------------------------------------------------------------------------- */

export interface MetricItem {
  label: ReactNode;
  value: ReactNode;
  detail?: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "accent";
  hint?: string;
}

/** A row of key figures separated by hairlines (not boxed tiles). */
export function Metrics({ items }: { items: MetricItem[] }) {
  const tone = { neutral: "text-ink", ok: "text-ok", warn: "text-warn", accent: "text-accent" };
  return (
    <dl className="grid grid-cols-2 gap-y-4 border-y border-line py-3.5 sm:flex sm:flex-wrap sm:divide-x sm:divide-line">
      {items.map((item, index) => (
        <div key={index} className="min-w-0 pr-6 sm:px-6 sm:first:pl-0">
          <dt className="flex items-center gap-1 text-[12px] text-ink-3">
            {item.label}
            {item.hint && <InfoTip>{item.hint}</InfoTip>}
          </dt>
          <dd className={`tabular mt-0.5 text-[17px] leading-snug font-semibold ${tone[item.tone ?? "neutral"]}`}>
            {item.value}
          </dd>
          {item.detail && <dd className="mt-0.5 max-w-[22ch] truncate text-[12px] text-ink-3">{item.detail}</dd>}
        </div>
      ))}
    </dl>
  );
}

/** Compact horizontal score indicator. `signed` draws a centre line for values in [-1, 1]. */
export function ScoreBar({
  value,
  max = 1,
  signed = false,
  width = 72,
  tone = "accent",
}: {
  value: number | null | undefined;
  max?: number;
  signed?: boolean;
  width?: number;
  tone?: "accent" | "muted";
}) {
  const v = typeof value === "number" && Number.isFinite(value) ? value : 0;
  const fill = tone === "accent" ? "var(--accent)" : "var(--ink-3)";
  if (signed) {
    const half = Math.min(Math.abs(v) / max, 1) * 50;
    return (
      <span className="relative inline-block h-1.5 shrink-0 rounded-full bg-surface-3" style={{ width }} aria-hidden>
        <span className="absolute top-[-2px] bottom-[-2px] left-1/2 w-px bg-line-strong" />
        <span
          className="absolute top-0 bottom-0 rounded-full"
          style={{
            width: `${half}%`,
            left: v >= 0 ? "50%" : undefined,
            right: v < 0 ? "50%" : undefined,
            background: v >= 0 ? fill : "var(--div-neg-2)",
          }}
        />
      </span>
    );
  }
  return (
    <span className="relative inline-block h-1.5 shrink-0 rounded-full bg-surface-3" style={{ width }} aria-hidden>
      <span
        className="absolute top-0 bottom-0 left-0 rounded-full"
        style={{ width: `${Math.max(0, Math.min(v / max, 1)) * 100}%`, background: fill }}
      />
    </span>
  );
}

/** A number with its bar, right-aligned for table cells. */
export function Score({
  value,
  text,
  max,
  signed,
  tone,
}: {
  value: number | null | undefined;
  text: string;
  max?: number;
  signed?: boolean;
  tone?: "accent" | "muted";
}) {
  return (
    <span className="inline-flex items-center justify-end gap-2.5">
      <span className="tabular w-10 text-right">{text}</span>
      <ScoreBar value={value} max={max} signed={signed} tone={tone} />
    </span>
  );
}

/**
 * Small (i) with an explanation on hover or keyboard focus. The tooltip is positioned against
 * the viewport, so scrolling tables neither clip it nor gain a scrollbar from it.
 */
export function InfoTip({ children, side = "top" }: { children: ReactNode; side?: "top" | "bottom" }) {
  const anchor = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number; below: boolean } | null>(null);
  const width = 256;

  const show = () => {
    const rect = anchor.current?.getBoundingClientRect();
    if (!rect) return;
    const left = Math.min(Math.max(8, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 8);
    const below = side === "bottom" || rect.top < 96;
    setPosition({ left, top: below ? rect.bottom + 6 : rect.top - 6, below });
  };
  const hide = () => setPosition(null);

  return (
    <span className="inline-flex align-middle" onMouseEnter={show} onMouseLeave={hide}>
      <button
        ref={anchor}
        type="button"
        className="inline-flex text-ink-3 hover:text-ink-2 focus-visible:text-ink-2"
        aria-label="More information"
        onFocus={show}
        onBlur={hide}
        onClick={(event) => event.stopPropagation()}
      >
        <Info className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
      </button>
      {position && (
        <span
          role="tooltip"
          className="pointer-events-none fixed z-50 rounded-md bg-ink px-2.5 py-2 text-left text-[12px] leading-snug font-normal tracking-normal whitespace-normal text-bg normal-case shadow-sm"
          style={{
            width,
            left: position.left,
            top: position.top,
            transform: position.below ? undefined : "translateY(-100%)",
          }}
        >
          {children}
        </span>
      )}
    </span>
  );
}

/** Neutral metadata tag. Use sparingly; most metadata reads better as plain text. */
export function Tag({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "accent" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-px text-[11.5px] leading-[1.45] whitespace-nowrap ${
        tone === "accent" ? "border-accent-line text-accent" : "border-line text-ink-2"
      }`}
    >
      {children}
    </span>
  );
}

export function Mono({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <code className={`font-mono text-[12px] ${className}`}>{children}</code>;
}

/** Inline status: a small dot and label. */
export function Status({ tone, children }: { tone: "ok" | "warn" | "danger" | "neutral"; children: ReactNode }) {
  const dot = { ok: "bg-ok", warn: "bg-warn", danger: "bg-danger", neutral: "bg-ink-3" }[tone];
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] whitespace-nowrap text-ink-2">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------------------------------
 * Messages and states
 * ------------------------------------------------------------------------------------- */

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn" | "danger";
  title?: ReactNode;
  children: ReactNode;
}) {
  const rule = { info: "border-line-strong", warn: "border-warn", danger: "border-danger" }[tone];
  return (
    <div className={`border-l-2 py-0.5 pl-3 text-[13px] leading-relaxed text-ink-2 ${rule}`}>
      {title && <p className="font-medium text-ink">{title}</p>}
      <div>{children}</div>
    </div>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-[13px] text-ink-3" role="status">
      <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg bg-surface-2 px-6 py-12 text-center">
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-[52ch] text-[13px] text-ink-3">{children}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------------------------------
 * Controls
 * ------------------------------------------------------------------------------------- */

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="mb-1.5 block text-[12.5px] font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[12px] leading-snug text-ink-3">{hint}</span>}
    </label>
  );
}

const CONTROL =
  "h-8 w-full rounded-md border border-line-strong bg-surface px-2.5 text-[13.5px] text-ink placeholder:text-ink-3 hover:border-ink-3 focus:border-accent focus:shadow-[0_0_0_3px_var(--focus)] focus:outline-none";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} pr-7 ${props.className ?? ""}`} />;
}

export function Checkbox({ label, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="flex items-start gap-2 text-[13px] text-ink-2">
      <input type="checkbox" {...props} className="mt-[3px] h-3.5 w-3.5 shrink-0 accent-[var(--accent)]" />
      <span>
        {label}
        {hint && <span className="block text-[12px] text-ink-3">{hint}</span>}
      </span>
    </label>
  );
}

export function Button({
  loading,
  children,
  variant = "primary",
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
}) {
  const styles = {
    primary: "bg-accent text-accent-ink hover:bg-accent-hover",
    secondary: "border border-line-strong bg-surface text-ink hover:border-ink-3",
    ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
  }[variant];
  const sizes = size === "sm" ? "h-7 px-2.5 text-[12.5px]" : "h-8 px-3.5 text-[13.5px]";
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${sizes} ${props.className ?? ""}`}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

/** Text button that reveals more (parameters, method notes). */
export function DisclosureButton({
  open,
  onToggle,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={onToggle}
      className="inline-flex items-center gap-1 text-[12.5px] text-ink-2 hover:text-ink"
    >
      {children}
      <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
    </button>
  );
}

/** Small segmented control (switching views within a section). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode; title?: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md bg-surface-3 p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          title={option.title}
          onClick={() => onChange(option.value)}
          className={`h-6 rounded-[3px] px-2.5 text-[12.5px] whitespace-nowrap ${
            value === option.value ? "bg-surface font-medium text-ink shadow-[0_1px_1px_rgba(0,0,0,0.06)]" : "text-ink-3 hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Underlined tabs for switching between result views. */
export function Tabs<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: ReactNode; title?: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="tablist" className="flex gap-5 border-b border-line">
      {options.map((option) => (
        <button
          key={option.value}
          role="tab"
          type="button"
          aria-selected={value === option.value}
          title={option.title}
          onClick={() => onChange(option.value)}
          className={`-mb-px border-b-2 pb-2 text-[13.5px] ${
            value === option.value ? "border-accent font-medium text-ink" : "border-transparent text-ink-3 hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------------------------------
 * Tables
 * ------------------------------------------------------------------------------------- */

/** Table wrapper: horizontal rules only, scrolls sideways on narrow screens. */
export function TableFrame({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto border-y border-line">{children}</div>;
}

export const TABLE = "w-full text-[13.5px]";
export const THEAD = "border-b border-line text-left";
export const TH = "px-3 py-2 text-[12px] font-medium whitespace-nowrap text-ink-3 first:pl-2 last:pr-2";
export const TD = "px-3 py-2.5 align-top first:pl-2 last:pr-2";
export const TR = "border-b border-line last:border-0";

/** Props that make a table row selectable by click or keyboard. */
export function selectableRow(selected: boolean, onSelect: () => void) {
  return {
    onClick: onSelect,
    onKeyDown: (event: KeyboardEvent) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect();
      }
    },
    tabIndex: 0,
    "aria-selected": selected,
    className: `${TR} cursor-pointer outline-none focus-visible:bg-surface-2 ${
      selected ? "bg-accent-soft shadow-[inset_2px_0_0_var(--accent)]" : "hover:bg-surface-2"
    }`,
  };
}

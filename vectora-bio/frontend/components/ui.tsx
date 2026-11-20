"use client";

import { ChevronRight, Info, Loader2, type LucideIcon, Plus } from "lucide-react";
import { useRef, useState } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  KeyboardEvent,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

/* ---------------------------------------------------------------------------------------
 * Page structure: hierarchy comes from type, rules and spacing, not boxes.
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
    <header className="mb-9 border-b border-line pb-7">
      {context && (
        <p className="eyebrow mb-4 flex items-center gap-3">
          <span className="h-px w-8 bg-accent" aria-hidden />
          {context}
        </p>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-[34px] leading-[1.05] font-light tracking-[-0.035em] text-ink sm:text-[42px]">{title}</h1>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {description && <p className="mt-3 max-w-[60ch] text-[15px] leading-relaxed text-ink-2">{description}</p>}
    </header>
  );
}

/** A titled region of a page, opened by a hairline rule. `plain` drops the rule. */
export function Section({
  title,
  description,
  actions,
  children,
  className = "",
  plain = false,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  plain?: boolean;
}) {
  return (
    <section className={`min-w-0 ${plain ? "" : "border-t border-line pt-5"} ${className}`}>
      {(title || actions) && (
        <div className="mb-5 flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
          <div className="min-w-0">
            {title && <h2 className="text-[20px] leading-tight font-normal tracking-[-0.02em] text-ink">{title}</h2>}
            {description && <p className="mt-1 text-[13px] text-ink-3">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-3 text-[12.5px] text-ink-3">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** The one framed surface: the query area of an analysis. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`border border-line-strong bg-surface ${className}`}>{children}</div>;
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

/** Key figures in a shared-border grid: small uppercase label, large light number. */
export function Metrics({ items }: { items: MetricItem[] }) {
  const tone = { neutral: "text-ink", ok: "text-ok", warn: "text-warn", accent: "text-accent" };
  return (
    <dl className="grid grid-cols-2 border-t border-l border-line sm:grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))]">
      {items.map((item, index) => (
        <div key={index} className="min-w-0 border-r border-b border-line px-4 py-4">
          <dt className="eyebrow flex items-center gap-1.5">
            <span className="annot text-[10px]">{String(index + 1).padStart(2, "0")}</span>
            {item.label}
            {item.hint && <InfoTip>{item.hint}</InfoTip>}
          </dt>
          <dd className={`tabular mt-3 text-[30px] leading-none font-light tracking-[-0.03em] ${tone[item.tone ?? "neutral"]}`}>
            {item.value}
          </dd>
          {item.detail && <dd className="mt-2 truncate text-[12px] text-ink-3">{item.detail}</dd>}
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
  const fill = tone === "accent" ? "var(--sage)" : "var(--ink-3)";
  if (signed) {
    const half = Math.min(Math.abs(v) / max, 1) * 50;
    return (
      <span className="relative inline-block h-1 shrink-0 bg-surface-3" style={{ width }} aria-hidden>
        <span className="absolute top-[-3px] bottom-[-3px] left-1/2 w-px bg-line-strong" />
        <span
          className="absolute top-0 bottom-0"
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
    <span className="relative inline-block h-1 shrink-0 bg-surface-3" style={{ width }} aria-hidden>
      <span
        className="absolute top-0 bottom-0 left-0"
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
        className="inline-flex text-ink-3 normal-case hover:text-ink focus-visible:text-ink"
        aria-label="More information"
        onFocus={show}
        onBlur={hide}
        onClick={(event) => event.stopPropagation()}
      >
        <Info className="h-3.5 w-3.5" strokeWidth={1.6} aria-hidden />
      </button>
      {position && (
        <span
          role="tooltip"
          className="pointer-events-none fixed z-50 bg-ink px-3 py-2 text-left text-[12px] leading-snug font-normal tracking-normal whitespace-normal text-bg normal-case shadow-pop"
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
      className={`inline-flex items-center gap-1 border px-1.5 py-px text-[11px] leading-[1.5] whitespace-nowrap ${
        tone === "accent" ? "border-accent-line text-accent" : "border-line-strong text-ink-2"
      }`}
    >
      {children}
    </span>
  );
}

/** Two small dots: the separator between items in a mono meta line ("PLATE • • WELL"). */
export function Dots({ className = "" }: { className?: string }) {
  return (
    <span className={`mx-2 inline-flex shrink-0 items-center gap-[3px] align-middle opacity-60 ${className}`} aria-hidden>
      <span className="h-[3px] w-[3px] rounded-full bg-current" />
      <span className="h-[3px] w-[3px] rounded-full bg-current" />
    </span>
  );
}

/** Mono uppercase readout: items joined by dot connectors. */
export function MetaLine({ items, className = "" }: { items: ReactNode[]; className?: string }) {
  const shown = items.filter((item) => item !== null && item !== undefined && item !== false && item !== "");
  return (
    <span className={`annot inline-flex flex-wrap items-center ${className}`}>
      {shown.map((item, index) => (
        <span key={index} className="inline-flex items-center">
          {index > 0 && <Dots />}
          {item}
        </span>
      ))}
    </span>
  );
}

/** "+" registration marks at the four corners of a positioned container. */
export function Crosshairs({ className = "text-line-strong", inset = "-6px" }: { className?: string; inset?: string }) {
  const mark = "pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2";
  const positions = [
    { left: inset, top: inset },
    { left: `calc(100% - ${inset})`, top: inset },
    { left: inset, top: `calc(100% - ${inset})` },
    { left: `calc(100% - ${inset})`, top: `calc(100% - ${inset})` },
  ];
  return (
    <>
      {positions.map((style, index) => (
        <svg key={index} viewBox="0 0 12 12" className={`${mark} ${className}`} style={style} aria-hidden>
          <path d="M6 0v12M0 6h12" stroke="currentColor" strokeWidth="1" />
        </svg>
      ))}
    </>
  );
}

export function Mono({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <code className={`font-mono text-[12px] ${className}`}>{children}</code>;
}

/** Inline status: a small dot and label. */
export function Status({ tone, children }: { tone: "ok" | "warn" | "danger" | "neutral"; children: ReactNode }) {
  const dot = { ok: "bg-ok", warn: "bg-warn", danger: "bg-danger", neutral: "bg-ink-3" }[tone];
  return (
    <span className="inline-flex items-center gap-2 font-mono text-[10.5px] tracking-[0.06em] whitespace-nowrap text-ink-2 uppercase">
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
  const rule = { info: "border-sage", warn: "border-warn", danger: "border-danger" }[tone];
  return (
    <div className={`border-l-2 py-0.5 pl-4 text-[13.5px] leading-relaxed text-ink-2 ${rule}`}>
      {title && <p className="font-medium text-ink">{title}</p>}
      <div>{children}</div>
    </div>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 border-t border-line py-10 text-[13px] text-ink-3" role="status">
      <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.6} aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="border-y border-line py-14 text-center">
      <p className="eyebrow">Nothing here yet</p>
      <p className="mt-3 text-[22px] font-light tracking-[-0.02em] text-ink">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-[52ch] text-[13.5px] text-ink-3">{children}</div>}
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
      <span className="eyebrow mb-2 block leading-4">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-[12px] leading-snug text-ink-3">{hint}</span>}
    </label>
  );
}

const CONTROL =
  "h-10 w-full rounded-md border border-line-strong bg-surface px-3 text-[14px] text-ink placeholder:text-ink-3 hover:border-ink-3 focus:border-ink focus:shadow-[0_0_0_3px_var(--focus)] focus:outline-none";

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
  // Primary and secondary are pills with a mono uppercase label; ghost stays a plain text button.
  const styles = {
    primary: "rounded-full bg-ink font-mono tracking-[0.08em] text-bg uppercase hover:bg-accent hover:text-accent-ink",
    secondary:
      "rounded-full border border-ink font-mono tracking-[0.08em] text-ink uppercase hover:bg-ink hover:text-bg",
    ghost: "rounded-md text-ink-2 hover:bg-surface-2 hover:text-ink",
  }[variant];
  const sizes =
    variant === "ghost"
      ? size === "sm"
        ? "h-8 px-3 text-[12.5px]"
        : "h-10 px-4 text-[13.5px]"
      : size === "sm"
        ? "h-8 px-4 text-[10.5px]"
        : "h-10 px-6 text-[11.5px]";
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-medium whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${sizes} ${props.className ?? ""}`}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

/** Uppercase text toggle that reveals more (parameters, method notes). The + turns into ×. */
export function DisclosureButton({
  open,
  onToggle,
  icon: Icon,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  icon?: LucideIcon;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={onToggle}
      className={`group inline-flex h-9 items-center gap-2 border-b font-mono text-[11px] font-medium tracking-[0.08em] uppercase ${
        open ? "border-accent text-accent" : "border-line-strong text-ink-2 hover:border-ink hover:text-ink"
      }`}
    >
      {Icon && <Icon className="h-3.5 w-3.5" strokeWidth={1.6} aria-hidden />}
      {children}
      <Plus
        className={`h-3.5 w-3.5 text-accent ${open ? "rotate-45" : "group-hover:rotate-90"}`}
        strokeWidth={1.8}
        aria-hidden
      />
    </button>
  );
}

/**
 * The expand control at the end of a table row: a small square; an invisible margin around it
 * (the ::before box) widens the hover and click target without moving layout.
 */
export function RowExpander({ open, onToggle, label }: { open: boolean; onToggle?: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onToggle?.();
      }}
      aria-expanded={open}
      aria-label={label}
      title={open ? "Hide details" : "Show details"}
      className={`relative inline-flex h-7 w-7 items-center justify-center rounded-full border before:absolute before:-inset-2 before:rounded-full before:content-[''] ${
        open ? "border-ink bg-ink text-bg" : "border-line-strong text-ink-2 hover:border-ink hover:text-ink"
      }`}
    >
      <ChevronRight className={`h-4 w-4 ${open ? "rotate-90" : ""}`} strokeWidth={1.8} aria-hidden />
    </button>
  );
}

/** Small view switch drawn as underlined labels. */
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
    <div role="radiogroup" aria-label={label} className="inline-flex gap-4">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          title={option.title}
          onClick={() => onChange(option.value)}
          className={`h-7 border-b text-[12.5px] whitespace-nowrap ${
            value === option.value ? "border-accent font-medium text-ink" : "border-transparent text-ink-3 hover:text-ink"
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
    <div role="tablist" className="flex gap-6 border-b border-line">
      {options.map((option) => (
        <button
          key={option.value}
          role="tab"
          type="button"
          aria-selected={value === option.value}
          title={option.title}
          onClick={() => onChange(option.value)}
          className={`-mb-px border-b-2 pb-2.5 text-[13.5px] ${
            value === option.value ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink"
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
export const TH =
  "px-3 py-2.5 font-mono text-[10.5px] font-medium tracking-[0.08em] whitespace-nowrap text-ink-3 uppercase first:pl-2 last:pr-2";
export const TD = "px-3 py-3 align-top first:pl-2 last:pr-2";
export const TR = "border-b border-line last:border-0";
/** Cell holding a RowExpander: extra right padding so its widened hit area stays inside the table. */
export const TD_EXPANDER = "w-12 px-3 py-2.5 pr-4! text-right align-top";

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
      selected ? "bg-accent-soft/70 shadow-[inset_2px_0_0_var(--accent)]" : "hover:bg-surface-2"
    }`,
  };
}

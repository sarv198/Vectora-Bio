import Link from "next/link";
import type { ReactNode } from "react";

/** The perturbation an analysis was run for: name, identifier and a few facts, without a box. */
export function QuerySummary({
  label,
  name,
  id,
  href,
  facts,
}: {
  label: string;
  name: string;
  id: string;
  href?: string;
  facts: { label: string; value: ReactNode }[];
}) {
  return (
    <div className="space-y-3">
      <div>
        <p className="text-[12px] text-ink-3">{label}</p>
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          {href ? (
            <Link href={href} className="text-[18px] font-semibold text-ink hover:text-accent">
              {name}
            </Link>
          ) : (
            <span className="text-[18px] font-semibold text-ink">{name}</span>
          )}
          {name !== id && <span className="font-mono text-[12px] text-ink-3">{id}</span>}
        </p>
      </div>
      <dl className="grid gap-x-8 gap-y-2 text-[13px] sm:grid-cols-2 lg:flex lg:flex-wrap">
        {facts.map((fact) => (
          <div key={fact.label} className="min-w-0 lg:max-w-[22rem]">
            <dt className="text-[12px] text-ink-3">{fact.label}</dt>
            <dd className="text-ink">{fact.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Two to four plain-language sentences stating what the result shows. */
export function Findings({ items }: { items: ReactNode[] }) {
  const shown = items.filter(Boolean);
  if (shown.length === 0) return null;
  return (
    <section aria-label="Key findings" className="rounded-lg bg-surface-2 px-4 py-3">
      <ul className="space-y-1 text-[13.5px] leading-relaxed text-ink-2">
        {shown.map((item, index) => (
          <li key={index} className="flex gap-2.5">
            <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-accent" aria-hidden />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Emphasised value inside a findings sentence. */
export function Em({ children }: { children: ReactNode }) {
  return <strong className="font-medium text-ink">{children}</strong>;
}

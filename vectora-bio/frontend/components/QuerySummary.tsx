import Link from "next/link";
import type { ReactNode } from "react";

import { InfoTip } from "@/components/ui";

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
  facts: { label: string; value: ReactNode; note?: string }[];
}) {
  return (
    <div className="space-y-4">
      <div>
        <p className="eyebrow">{label}</p>
        <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          {href ? (
            <Link href={href} className="text-[30px] leading-none font-light tracking-[-0.03em] text-ink hover:text-accent">
              {name}
            </Link>
          ) : (
            <span className="text-[30px] leading-none font-light tracking-[-0.03em] text-ink">{name}</span>
          )}
          {name !== id && <span className="annot">{id}</span>}
        </p>
      </div>
      <dl className="grid gap-x-8 gap-y-3 text-[13.5px] sm:grid-cols-2 lg:flex lg:flex-wrap">
        {facts.map((fact) => (
          <div key={fact.label} className="min-w-0 lg:max-w-[22rem]">
            <dt className="eyebrow flex items-center gap-1">
              {fact.label}
              {fact.note && <InfoTip>{fact.note}</InfoTip>}
            </dt>
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
    <section aria-label="Key findings" className="grid gap-3 border-y border-line py-5 sm:grid-cols-[10rem_minmax(0,1fr)]">
      <p className="eyebrow flex items-center gap-3 pt-1">
        <span className="h-px w-6 bg-accent" aria-hidden />
        Key findings
      </p>
      <ol className="space-y-2 text-[15px] leading-relaxed text-ink-2">
        {shown.map((item, index) => (
          <li key={index} className="flex gap-4">
            <span className="annot shrink-0 pt-[5px]">{String(index + 1).padStart(2, "0")}</span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Emphasised value inside a findings sentence. */
export function Em({ children }: { children: ReactNode }) {
  return <strong className="font-medium text-ink">{children}</strong>;
}

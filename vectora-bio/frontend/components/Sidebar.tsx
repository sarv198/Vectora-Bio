"use client";

import {
  ChartColumn,
  Dna,
  FlaskConical,
  GitCompareArrows,
  Grid3x3,
  House,
  type LucideIcon,
  Network,
  Target,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/ThemeToggle";
import { api } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const SECTIONS: { title: string | null; items: NavItem[] }[] = [
  { title: null, items: [{ href: "/", label: "Overview", icon: House }] },
  {
    title: "Analysis",
    items: [
      { href: "/similarity", label: "Compound similarity", icon: GitCompareArrows },
      { href: "/targets", label: "Drug-to-gene matching", icon: Target },
      { href: "/moa", label: "Mechanism of action", icon: Network },
      { href: "/rescue", label: "Phenotypic rescue", icon: Undo2 },
      { href: "/evaluation", label: "Evaluation", icon: ChartColumn },
    ],
  },
  {
    title: "Library",
    items: [
      { href: "/plates", label: "Plates", icon: Grid3x3 },
      { href: "/compounds", label: "Compounds", icon: FlaskConical },
      { href: "/genes", label: "Genes", icon: Dna },
    ],
  },
];

/** CellScope wordmark: a single well outline with an off-centre cell, drawn in the accent. */
export function Wordmark() {
  return (
    <Link href="/" className="flex items-center gap-2 text-ink">
      <svg viewBox="0 0 18 18" className="h-[18px] w-[18px] text-accent" aria-hidden>
        <circle cx="9" cy="9" r="7.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="10.6" cy="7.6" r="2.6" fill="currentColor" />
      </svg>
      <span className="text-[15px] font-semibold tracking-[-0.01em]">CellScope</span>
    </Link>
  );
}

function ConnectionStatus() {
  const { data, error } = useApiQuery(() => api.health(), []);
  const profiles = data?.datasets.filter((d) => d.available) ?? [];
  const n = profiles.reduce((sum, d) => sum + (d.n_rows ?? 0), 0);
  const dbOk = data?.database.status === "ok";
  const tone = error ? "bg-danger" : !data ? "bg-ink-3" : dbOk && profiles.length ? "bg-ok" : "bg-warn";
  const text = error
    ? "API not reachable"
    : !data
      ? "Connecting"
      : `${dbOk ? "Connected" : "Database unavailable"} · ${formatCount(n)} profiles`;
  return (
    <p className="flex items-center gap-2 text-[12px] text-ink-3" title={error ? error.message : undefined}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone}`} aria-hidden />
      <span className="truncate">{text}</span>
    </p>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="z-30 border-b border-line bg-sidebar md:sticky md:top-0 md:flex md:h-screen md:w-[220px] md:shrink-0 md:flex-col md:border-r md:border-b-0">
      <div className="flex items-center justify-between px-4 py-3 md:px-5 md:pt-5 md:pb-6">
        <Wordmark />
        <div className="md:hidden">
          <ThemeToggle />
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-2 md:block md:flex-1 md:space-y-5 md:overflow-y-auto md:pb-4">
        {SECTIONS.map((section, index) => (
          <div key={section.title ?? index} className="flex gap-1 md:block md:space-y-px">
            {section.title && <p className="hidden px-2 pb-1 text-[11.5px] font-medium text-ink-3 md:block">{section.title}</p>}
            {section.items.map(({ href, label, icon: Icon }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex shrink-0 items-center gap-2.5 rounded-md px-2 py-[5px] text-[13.5px] whitespace-nowrap ${
                    active ? "bg-surface font-medium text-ink shadow-[0_0_0_1px_var(--line)]" : "text-ink-2 hover:bg-surface-3/60 hover:text-ink"
                  }`}
                >
                  <Icon
                    className={`h-4 w-4 shrink-0 ${active ? "text-accent" : "text-ink-3"}`}
                    strokeWidth={1.75}
                    aria-hidden
                  />
                  {label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="hidden space-y-3 border-t border-line px-5 py-4 md:block">
        <ConnectionStatus />
        <ThemeToggle />
      </div>
    </aside>
  );
}

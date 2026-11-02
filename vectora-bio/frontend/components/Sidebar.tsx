"use client";

import {
  Activity,
  BarChart3,
  Crosshair,
  Dna,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  Network,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS = [
  {
    title: "Overview",
    items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    title: "Data",
    items: [
      { href: "/compounds", label: "Compounds", icon: FlaskConical },
      { href: "/genes", label: "Genes", icon: Dna },
    ],
  },
  {
    title: "Analysis",
    items: [
      { href: "/similarity", label: "Compound similarity", icon: GitCompareArrows },
      { href: "/targets", label: "Target prioritization", icon: Crosshair },
      { href: "/moa", label: "MoA inference", icon: Network },
      { href: "/rescue", label: "Phenotypic rescue", icon: Undo2 },
      { href: "/evaluation", label: "Evaluation", icon: BarChart3 },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="border-b border-line bg-surface md:sticky md:top-0 md:h-screen md:w-64 md:shrink-0 md:border-r md:border-b-0">
      <div className="flex items-center gap-2 px-5 py-4 md:py-6">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
          <Activity className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <p className="text-sm font-semibold tracking-tight">Vectora Bio</p>
          <p className="text-xs text-ink-3">Phenotypic profiling</p>
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:block md:space-y-5 md:overflow-visible md:pb-0">
        {SECTIONS.map((section) => (
          <div key={section.title} className="flex gap-1 md:block md:space-y-0.5">
            <p className="hidden px-2 pb-1 text-[11px] font-medium tracking-wider text-ink-3 uppercase md:block">
              {section.title}
            </p>
            {section.items.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex shrink-0 items-center gap-2.5 rounded-md px-2 py-1.5 text-sm whitespace-nowrap transition-colors ${
                  isActive(href)
                    ? "bg-accent-soft font-medium text-accent"
                    : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                {label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}

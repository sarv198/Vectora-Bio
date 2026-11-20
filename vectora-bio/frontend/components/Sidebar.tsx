"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Dots } from "@/components/ui";
import { api } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

interface NavItem {
  href: string;
  label: string;
}

const SECTIONS: { title: string | null; items: NavItem[] }[] = [
  { title: null, items: [{ href: "/", label: "Overview" }] },
  {
    title: "Analysis",
    items: [
      { href: "/similarity", label: "Compound similarity" },
      { href: "/targets", label: "Drug-to-gene matching" },
      { href: "/moa", label: "Mechanism of action" },
      { href: "/rescue", label: "Phenotypic rescue" },
      { href: "/evaluation", label: "Evaluation" },
    ],
  },
  {
    title: "Library",
    items: [
      { href: "/plates", label: "Plates" },
      { href: "/compounds", label: "Compounds" },
      { href: "/genes", label: "Genes" },
    ],
  },
];

/** vectora-bio wordmark: lowercase, light, with the suffix in the accent. */
export function Wordmark() {
  return (
    <Link href="/" className="block text-sidebar-ink">
      <span className="block text-[22px] leading-none font-light tracking-[-0.04em]">
        vectora<span className="text-sidebar-accent">-bio</span>
      </span>
      <span className="mt-2 block font-mono text-[10px] tracking-[0.12em] text-sidebar-ink-2 uppercase">
        Phenotypic drug discovery
      </span>
    </Link>
  );
}

function ConnectionStatus() {
  const { data, error } = useApiQuery(() => api.health(), []);
  const profiles = data?.datasets.filter((d) => d.available) ?? [];
  const n = profiles.reduce((sum, d) => sum + (d.n_rows ?? 0), 0);
  const dbOk = data?.database.status === "ok";
  const tone = error ? "bg-danger" : !data ? "bg-sidebar-ink-2" : dbOk && profiles.length ? "bg-ok" : "bg-warn";
  const text = error ? (
    "API not reachable"
  ) : !data ? (
    "Connecting"
  ) : (
    <>
      {dbOk ? "Connected" : "Database unavailable"}
      <Dots />
      {formatCount(n)} profiles
    </>
  );
  return (
    <p className="flex items-center gap-2 font-mono text-[10.5px] tracking-[0.06em] text-sidebar-ink-2 uppercase" title={error ? error.message : undefined}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone}`} aria-hidden />
      <span className="flex min-w-0 items-center truncate">{text}</span>
    </p>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  let index = 0;

  return (
    <aside className="z-30 bg-sidebar text-sidebar-ink md:sticky md:top-0 md:flex md:h-screen md:w-[248px] md:shrink-0 md:flex-col">
      <div className="flex items-center justify-between px-5 py-4 md:px-6 md:pt-8 md:pb-9">
        <Wordmark />
        <div className="md:hidden">
          <ThemeToggle />
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:block md:flex-1 md:space-y-7 md:overflow-y-auto md:px-0 md:pb-6">
        {SECTIONS.map((section, sectionIndex) => (
          <div key={section.title ?? sectionIndex} className="flex gap-1 md:block">
            {section.title && (
              <p className="hidden border-b border-sidebar-line px-6 pb-2 font-mono text-[10px] tracking-[0.14em] text-sidebar-ink-2 uppercase md:mb-1 md:block">
                {section.title}
              </p>
            )}
            {section.items.map(({ href, label }) => {
              const active = isActive(href);
              index += 1;
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`group relative flex shrink-0 items-center gap-3 px-3 py-[7px] font-mono text-[11.5px] tracking-[0.06em] whitespace-nowrap uppercase md:px-6 ${
                    active ? "text-sidebar-ink" : "text-sidebar-ink-2 hover:text-sidebar-ink"
                  }`}
                >
                  <span
                    className={`absolute top-1/2 left-0 hidden h-5 w-[2px] -translate-y-1/2 bg-sidebar-accent md:block ${
                      active ? "opacity-100" : "opacity-0"
                    }`}
                    aria-hidden
                  />
                  <span
                    className={`hidden w-5 shrink-0 font-mono text-[10px] tracking-[0.04em] md:inline ${
                      active ? "text-sidebar-accent" : "text-sidebar-ink-2/70"
                    }`}
                  >
                    {String(index).padStart(2, "0")}
                  </span>
                  {label}
                  <span
                    className={`ml-auto hidden h-[3px] w-[3px] rounded-full bg-sidebar-accent md:block ${active ? "" : "opacity-0"}`}
                    aria-hidden
                  />
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="hidden space-y-4 border-t border-sidebar-line px-6 py-5 md:block">
        <ConnectionStatus />
        <ThemeToggle />
      </div>
    </aside>
  );
}

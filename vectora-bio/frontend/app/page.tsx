"use client";

import {
  BarChart3,
  CheckCircle2,
  Crosshair,
  Database,
  GitCompareArrows,
  LayoutDashboard,
  Network,
  RefreshCw,
  Undo2,
  XCircle,
} from "lucide-react";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { Badge, Button, Card, LoadingState, Mono, PageHeader } from "@/components/ui";
import { API_BASE_URL, api } from "@/lib/api";
import { formatCount, humanize } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

const CAPABILITIES = [
  {
    href: "/similarity",
    title: "Compound similarity",
    description: "Rank compounds by phenotypic profile similarity.",
    icon: GitCompareArrows,
    needs: ["compound_profiles"],
  },
  {
    href: "/targets",
    title: "Target prioritization",
    description: "Match compounds to genetic perturbations and rank candidate targets.",
    icon: Crosshair,
    needs: ["compound_profiles", "genetic_profiles"],
  },
  {
    href: "/moa",
    title: "MoA inference",
    description: "Infer mechanisms from annotated phenotypic neighbours.",
    icon: Network,
    needs: ["compound_profiles"],
  },
  {
    href: "/rescue",
    title: "Phenotypic rescue",
    description: "Find compounds that oppose a perturbation phenotype.",
    icon: Undo2,
    needs: ["compound_profiles", "genetic_profiles", "control_profiles"],
  },
  {
    href: "/evaluation",
    title: "Evaluation",
    description: "Review benchmark metrics recorded on imported data.",
    icon: BarChart3,
    needs: [],
  },
];

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 className="h-4 w-4 text-ok" aria-label="available" />
  ) : (
    <XCircle className="h-4 w-4 text-ink-3" aria-label="not available" />
  );
}

export default function DashboardPage() {
  const { data, error, loading, reload } = useApiQuery(() => api.health(), []);
  const available = new Set(data?.datasets.filter((d) => d.available).map((d) => d.name));
  const nothingLoaded = data && available.size === 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Service status, imported datasets, and the analytical capabilities they unlock."
        icon={<LayoutDashboard className="h-5 w-5" />}
        actions={
          <Button variant="secondary" onClick={reload} loading={loading}>
            <RefreshCw className="h-4 w-4" aria-hidden /> Refresh
          </Button>
        }
      />

      {error ? (
        <ApiErrorNotice error={error} />
      ) : !data ? (
        <LoadingState />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <Card title="API">
              <div className="flex items-center gap-2">
                <Badge tone={data.status === "ok" ? "ok" : "warn"}>{data.status === "ok" ? "Healthy" : "Degraded"}</Badge>
                <span className="text-xs text-ink-3">
                  v{data.version} · {data.environment}
                </span>
              </div>
              <p className="mt-2 truncate font-mono text-xs text-ink-3">{API_BASE_URL}</p>
            </Card>
            <Card title="Database">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-ink-3" aria-hidden />
                <Badge tone={data.database.status === "ok" ? "ok" : "danger"}>{data.database.status}</Badge>
                <span className="text-xs text-ink-3">{data.database.dialect}</span>
              </div>
              {data.database.status === "ok" ? (
                <p className="tabular mt-2 text-sm text-ink-2">
                  {formatCount(data.database.compound_count)} compound records ·{" "}
                  {formatCount(data.database.genetic_perturbation_count)} genetic records
                </p>
              ) : (
                <p className="mt-2 text-xs text-ink-2">{data.database.message}</p>
              )}
            </Card>
            <Card title="Profile datasets">
              <ul className="space-y-1.5 text-sm">
                {data.datasets.map((dataset) => (
                  <li key={dataset.name} className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <StatusIcon ok={dataset.available} />
                      {humanize(dataset.profile_type)}
                    </span>
                    <span className="tabular text-xs text-ink-3">
                      {dataset.available
                        ? `${formatCount(dataset.n_rows)} × ${formatCount(dataset.n_features)}`
                        : "not imported"}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          {nothingLoaded && (
            <Card title="Getting started">
              <ol className="list-decimal space-y-2 pl-5 text-sm text-ink-2">
                <li>Download processed JUMP Cell Painting profiles locally into <Mono>data/raw/</Mono>.</li>
                <li>
                  Import profiles: <Mono>python -m app.pipeline.import_profiles --input … --profile-type compound</Mono>
                </li>
                <li>
                  Import metadata: <Mono>python -m app.pipeline.import_metadata compounds --input …</Mono>
                </li>
                <li>Refresh this page. See the README for the full walkthrough.</li>
              </ol>
            </Card>
          )}

          <div>
            <h2 className="mb-3 text-sm font-semibold">Capabilities</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {CAPABILITIES.map(({ href, title, description, icon: Icon, needs }) => {
                const missing = needs.filter((name) => !available.has(name));
                return (
                  <Link
                    key={href}
                    href={href}
                    className="group rounded-xl border border-line bg-surface p-4 transition hover:border-accent/50"
                  >
                    <div className="flex items-center justify-between">
                      <Icon className="h-5 w-5 text-accent" aria-hidden />
                      {needs.length > 0 &&
                        (missing.length === 0 ? <Badge tone="ok">Ready</Badge> : <Badge tone="warn">Needs data</Badge>)}
                    </div>
                    <p className="mt-3 text-sm font-semibold group-hover:text-accent">{title}</p>
                    <p className="mt-1 text-sm text-ink-2">{description}</p>
                    {missing.length > 0 && (
                      <p className="mt-2 text-xs text-ink-3">Missing: {missing.map(humanize).join(", ")}</p>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

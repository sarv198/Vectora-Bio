"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { LoadingState, Metrics, Mono, PageHeader, Section, Status, TABLE, TD, TR, TableFrame } from "@/components/ui";
import { API_BASE_URL, api } from "@/lib/api";
import { formatCount, humanize } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

const TOOLS = [
  {
    href: "/similarity",
    title: "Compound similarity",
    question: "Which compounds change cells the same way as this one?",
    needs: ["compound_profiles"],
  },
  {
    href: "/targets",
    title: "Drug-to-gene matching",
    question: "Which gene knockout or overexpression looks like this compound?",
    needs: ["compound_profiles", "genetic_profiles"],
  },
  {
    href: "/moa",
    title: "Mechanism of action",
    question: "What mechanism do the most similar annotated compounds suggest?",
    needs: ["compound_profiles"],
  },
  {
    href: "/rescue",
    title: "Phenotypic rescue",
    question: "Which compounds push cells back from a genetic perturbation's phenotype?",
    needs: ["compound_profiles", "genetic_profiles", "control_profiles"],
  },
  {
    href: "/evaluation",
    title: "Evaluation",
    question: "How well do these methods work on compounds they have not seen?",
    needs: [],
  },
];

export default function OverviewPage() {
  const { data, error, loading } = useApiQuery(() => api.health(), []);
  const plates = useApiQuery(() => api.listPlates(), []);
  const available = new Set(data?.datasets.filter((d) => d.available).map((d) => d.name));
  const dataset = (name: string) => data?.datasets.find((d) => d.name === name);
  const nothingLoaded = data && available.size === 0;

  return (
    <>
      <PageHeader
        title="Overview"
        description="Cell Painting profiles from chemical and genetic perturbation screens, and the analyses they support."
      />

      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : (
        <div className="space-y-10">
          <Metrics
            items={[
              { label: "Compounds", value: formatCount(dataset("compound_profiles")?.n_rows), detail: "consensus profiles" },
              { label: "Genetic reagents", value: formatCount(dataset("genetic_profiles")?.n_rows), detail: "CRISPR guides and ORFs" },
              { label: "Control profiles", value: formatCount(dataset("control_profiles")?.n_rows), detail: "negative controls" },
              { label: "Features", value: formatCount(dataset("compound_profiles")?.n_features), detail: "per profile" },
              {
                label: "Imaged plates",
                value: plates.data ? String(plates.data.length) : "n/a",
                detail: plates.data ? `${formatCount(plates.data.reduce((s, p) => s + p.n_wells, 0))} wells` : "well files missing",
              },
            ]}
          />

          {nothingLoaded && (
            <Section title="Getting started">
              <ol className="list-decimal space-y-1.5 pl-5 text-[13.5px] text-ink-2">
                <li>
                  Build the JUMP pilot subset:{" "}
                  <Mono>python -m app.pipeline.build_profiles --config config\phase1_cpjump1_u2os.toml</Mono>
                </li>
                <li>
                  Or import processed profiles: <Mono>python -m app.pipeline.import_profiles --input … --profile-type compound</Mono>
                </li>
                <li>Reload this page. The README has the full walkthrough.</li>
              </ol>
            </Section>
          )}

          <Section title="Analysis tools">
            <TableFrame>
              <table className={TABLE}>
                <tbody>
                  {TOOLS.map(({ href, title, question, needs }) => {
                    const missing = needs.filter((name) => !available.has(name));
                    return (
                      <tr key={href} className={`${TR} group hover:bg-surface-2`}>
                        <td className={`${TD} w-56 py-3`}>
                          <Link href={href} className="font-medium text-ink group-hover:text-accent">
                            {title}
                          </Link>
                        </td>
                        <td className={`${TD} py-3 text-ink-2`}>{question}</td>
                        <td className={`${TD} w-40 py-3 text-right`}>
                          {needs.length === 0 ? (
                            <Status tone="neutral">Uses the database</Status>
                          ) : missing.length === 0 ? (
                            <Status tone="ok">Ready</Status>
                          ) : (
                            <span title={`Missing: ${missing.map(humanize).join(", ")}`}>
                              <Status tone="warn">Needs data</Status>
                            </span>
                          )}
                        </td>
                        <td className={`${TD} w-8 py-3`}>
                          <Link href={href} aria-label={`Open ${title}`} className="text-ink-3 group-hover:text-accent">
                            <ArrowRight className="h-4 w-4" strokeWidth={1.75} aria-hidden />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableFrame>
          </Section>

          <div className="grid gap-10 lg:grid-cols-2">
            <Section title="Data">
              <dl className="divide-y divide-line border-y border-line text-[13.5px]">
                {data.datasets.map((d) => (
                  <div key={d.name} className="flex items-center justify-between gap-4 py-2">
                    <dt className="text-ink-2">{humanize(d.profile_type)} profiles</dt>
                    <dd className="tabular text-ink">
                      {d.available ? (
                        `${formatCount(d.n_rows)} x ${formatCount(d.n_features)}`
                      ) : (
                        <Status tone="warn">Not imported</Status>
                      )}
                    </dd>
                  </div>
                ))}
                <div className="flex items-center justify-between gap-4 py-2">
                  <dt className="text-ink-2">Cell images</dt>
                  <dd>
                    <Link href="/plates" className="text-accent hover:underline">
                      Browse plates
                    </Link>
                  </dd>
                </div>
              </dl>
            </Section>
            <Section title="Service">
              <dl className="divide-y divide-line border-y border-line text-[13.5px]">
                <div className="flex items-center justify-between gap-4 py-2">
                  <dt className="text-ink-2">API</dt>
                  <dd>
                    <Status tone={data.status === "ok" ? "ok" : "warn"}>
                      {data.status === "ok" ? "Healthy" : "Degraded"} · v{data.version}
                    </Status>
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-4 py-2">
                  <dt className="text-ink-2">Database</dt>
                  <dd>
                    {data.database.status === "ok" ? (
                      <Status tone="ok">
                        {data.database.dialect}: {formatCount(data.database.compound_count)} compounds,{" "}
                        {formatCount(data.database.genetic_perturbation_count)} reagents
                      </Status>
                    ) : (
                      <Status tone="danger">{data.database.message ?? "Unavailable"}</Status>
                    )}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-4 py-2">
                  <dt className="text-ink-2">Endpoint</dt>
                  <dd className="font-mono text-[12px] text-ink-3">{API_BASE_URL}</dd>
                </div>
              </dl>
            </Section>
          </div>
        </div>
      )}
    </>
  );
}

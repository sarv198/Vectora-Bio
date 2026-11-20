"use client";

import { ArrowDownRight, ArrowRight } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { Crosshairs, Dots, LoadingState, MetaLine, Metrics, Mono, Section, Status } from "@/components/ui";
import { API_BASE_URL, api, wellImageUrl } from "@/lib/api";
import { formatCount, humanize } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

const TOOLS: { href: string; title: string; question: string; needs: string[] }[] = [
  {
    href: "/similarity",
    title: "Compound similarity",
    question: "Find compounds that reproduce the same cellular phenotype, ranked by profile similarity.",
    needs: ["compound_profiles"],
  },
  {
    href: "/targets",
    title: "Drug-to-gene matching",
    question: "Nominate candidate targets by matching a compound to CRISPR knockouts and ORF overexpressions.",
    needs: ["compound_profiles", "genetic_profiles"],
  },
  {
    href: "/moa",
    title: "Mechanism of action",
    question: "Infer a likely mechanism from the annotated compounds closest in phenotype space.",
    needs: ["compound_profiles"],
  },
  {
    href: "/rescue",
    title: "Phenotypic rescue",
    question: "Rank compounds whose profile pushes cells opposite to a genetic perturbation.",
    needs: ["compound_profiles", "genetic_profiles", "control_profiles"],
  },
  {
    href: "/evaluation",
    title: "Evaluation",
    question: "Benchmark every method on held-out compounds against a simple baseline.",
    needs: [],
  },
];

/** The field shown in the hero: dyphylline, plate BR00117010, well F08, against its DMSO well. */
const HERO_FIELD = {
  plate: "BR00117010",
  well: "F08",
  field: 5,
  reference: "H18",
  channels: ["DNA", "ER", "Mito"],
  compoundId: "BRD-A00827783-001-24-6",
  name: "Dyphylline",
  note: "Adenosine receptor antagonist",
};

/** A real Cell Painting field in a viewfinder: registration marks outside, mono readouts inside. */
function HeroField() {
  const f = HERO_FIELD;
  const [state, setState] = useState<"loading" | "loaded" | "error">("loading");
  const image = useRef<HTMLImageElement>(null);
  const src = wellImageUrl({ plate: f.plate, well: f.well, field: f.field, channels: f.channels, size: 540, ref: f.reference });

  // The image can finish loading before hydration attaches onLoad; read its state on mount.
  useEffect(() => {
    const element = image.current;
    if (element?.complete) setState(element.naturalWidth > 0 ? "loaded" : "error");
  }, [src]);
  const readout = "pointer-events-none absolute z-[2] font-mono text-[10px] tracking-[0.08em] text-white/85 uppercase";
  return (
    <figure className="relative">
      <div className="relative p-3">
        <Crosshairs className="text-ink-3" inset="0px" />
        <div className="scanlines relative aspect-square overflow-hidden bg-viewer">
          {/* eslint-disable-next-line @next/next/no-img-element -- rendered by the API, not a static asset */}
          <img
            ref={image}
            src={src}
            alt={`${f.name}: ${f.channels.join(" + ")}, plate ${f.plate} well ${f.well} field ${f.field}`}
            className={`h-full w-full object-cover ${state === "loaded" ? "" : "invisible"}`}
            onLoad={() => setState("loaded")}
            onError={() => setState("error")}
          />
          {state !== "loaded" && (
            <div className="absolute inset-0 flex items-center justify-center font-mono text-[10.5px] tracking-[0.08em] text-white/50 uppercase">
              {state === "loading" ? "Acquiring field…" : "Field unavailable"}
            </div>
          )}
          <span className={`${readout} top-3 left-3`}>
            Field {String(f.field).padStart(2, "0")} / 09
          </span>
          <span className={`${readout} top-3 right-3`}>{f.channels.join(" · ")}</span>
          <span className={`${readout} bottom-3 left-3`}>
            {f.plate} <Dots /> {f.well}
          </span>
          <span className={`${readout} right-3 bottom-3 flex flex-col items-end gap-1`}>
            100 µm
            <span className="block h-px w-[15.5%] min-w-10 bg-white/85" />
          </span>
        </div>
      </div>
      <figcaption className="mt-3 flex items-center justify-between gap-3 px-3">
        <span className="subline">
          {f.name} <Dots /> {f.note}
        </span>
        <Link
          href={`/compounds/${encodeURIComponent(f.compoundId)}`}
          className="link-rule inline-flex shrink-0 items-center gap-1.5 font-mono text-[10.5px] tracking-[0.08em] text-ink uppercase"
        >
          Open
          <ArrowRight className="h-3 w-3 text-accent" strokeWidth={1.8} aria-hidden />
        </Link>
      </figcaption>
    </figure>
  );
}

/** Round-trip time of one health request, measured in the browser. */
function useLatency() {
  const [ms, setMs] = useState<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    api
      .health()
      .then(() => setMs(Math.round(performance.now() - start)))
      .catch(() => setMs(null));
  }, []);
  return ms;
}

function Hero({ readouts }: { readouts: ReactNode[] }) {
  return (
    <section className="mb-14 grid items-center gap-12 border-b border-line pb-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <div>
        <p className="eyebrow mb-6 flex items-center gap-3">
          <span className="h-px w-8 bg-accent" aria-hidden />
          Phenotypic drug discovery
        </p>
        <h1 className="dim text-[40px] leading-[1.04] font-light tracking-[-0.045em] sm:text-[54px]">
          Turn <span className="text-ink">cell images</span> into <span className="text-ink">drug discovery</span>{" "}
          hypotheses.
        </h1>
        <p className="mt-6 max-w-[54ch] text-[15.5px] leading-relaxed text-ink-2">
          vectora-bio reads Cell Painting morphology profiles from the JUMP pilot screen and ranks look-alike compounds,
          candidate targets, likely mechanisms and genetic rescuers, each with the evidence behind it and benchmarks on
          held-out compounds.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-4">
          <Link
            href="/similarity"
            className="inline-flex h-11 items-center gap-2.5 rounded-full bg-ink px-6 font-mono text-[11.5px] font-medium tracking-[0.08em] text-bg uppercase hover:bg-accent hover:text-accent-ink"
          >
            Start an analysis
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.8} aria-hidden />
          </Link>
          <Link
            href="/compounds"
            className="link-rule inline-flex items-center gap-2 font-mono text-[11.5px] tracking-[0.08em] text-ink uppercase"
          >
            Explore the library
            <ArrowDownRight className="h-3.5 w-3.5 text-accent" strokeWidth={1.8} aria-hidden />
          </Link>
        </div>
        <div className="mt-10 flex items-center gap-3 border-t border-line pt-4">
          <span className="relative flex h-1.5 w-1.5" aria-hidden>
            <span className="absolute inset-0 animate-ping rounded-full bg-ok opacity-50 motion-reduce:hidden" />
            <span className="relative h-1.5 w-1.5 rounded-full bg-ok" />
          </span>
          <MetaLine items={readouts} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-[440px] lg:justify-self-end">
        <HeroField />
      </div>
    </section>
  );
}

export default function OverviewPage() {
  const { data, error, loading } = useApiQuery(() => api.health(), []);
  const plates = useApiQuery(() => api.listPlates(), []);
  const available = new Set(data?.datasets.filter((d) => d.available).map((d) => d.name));
  const dataset = (name: string) => data?.datasets.find((d) => d.name === name);
  const nothingLoaded = data && available.size === 0;
  const latency = useLatency();
  const profiles = data?.datasets.filter((d) => d.available).reduce((sum, d) => sum + (d.n_rows ?? 0), 0);

  return (
    <>
      <Hero
        readouts={[
          error ? "API offline" : latency !== null ? `API ${latency} ms` : "API …",
          profiles ? `${formatCount(profiles)} profiles` : null,
          dataset("compound_profiles")?.n_features ? `${dataset("compound_profiles")?.n_features} features` : null,
          plates.data ? `${plates.data.length} plates` : null,
        ]}
      />

      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : (
        <div className="space-y-14">
          <div>
            <p className="eyebrow mb-4">Phenotypic reference set</p>
            <Metrics
              items={[
                { label: "Compounds", value: formatCount(dataset("compound_profiles")?.n_rows) },
                { label: "Genetic reagents", value: formatCount(dataset("genetic_profiles")?.n_rows) },
                { label: "Controls", value: formatCount(dataset("control_profiles")?.n_rows) },
                { label: "Features", value: formatCount(dataset("compound_profiles")?.n_features) },
                {
                  label: "Plates",
                  value: plates.data ? (
                    <Link href="/plates" className="hover:text-accent">
                      {plates.data.length}
                    </Link>
                  ) : (
                    "n/a"
                  ),
                  detail: plates.data ? `${formatCount(plates.data.reduce((s, p) => s + p.n_wells, 0))} wells` : "well files missing",
                },
              ]}
            />
          </div>

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

          <div>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
              <h2 className="dim text-[30px] leading-tight font-light tracking-[-0.03em]">
                One phenotypic fingerprint, <span className="text-ink">five discovery workflows.</span>
              </h2>
              <p className="eyebrow">Workflows · 01 — 05</p>
            </div>
            <ul className="grid border-t border-l border-line sm:grid-cols-2 lg:grid-cols-3">
              {TOOLS.map(({ href, title, question, needs }, index) => {
                const missing = needs.filter((name) => !available.has(name));
                return (
                  <li key={href} className="border-r border-b border-line">
                    <Link href={href} className="group flex h-full min-h-[190px] flex-col p-6 hover:bg-surface">
                      <span className="flex items-center justify-between gap-3">
                        <span className="annot">{String(index + 1).padStart(2, "0")}</span>
                        {missing.length === 0 ? (
                          <Status tone="ok">Ready</Status>
                        ) : (
                          <span title={`Missing: ${missing.map(humanize).join(", ")}`}>
                            <Status tone="warn">Needs data</Status>
                          </span>
                        )}
                      </span>
                      <span className="mt-6 text-[21px] leading-tight font-normal tracking-[-0.02em] text-ink group-hover:text-accent">
                        {title}
                      </span>
                      <span className="mt-2 flex-1 text-[13.5px] leading-relaxed text-ink-2">{question}</span>
                      <span className="mt-6 inline-flex items-center gap-2 text-[12px] font-medium tracking-[0.1em] text-ink uppercase">
                        Open
                        <ArrowRight className="h-3.5 w-3.5 text-accent group-hover:translate-x-1" strokeWidth={1.8} aria-hidden />
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="max-w-2xl">
            <Section title="Service">
              <dl className="divide-y divide-line text-[13.5px]">
                <div className="flex items-center justify-between gap-4 py-2.5">
                  <dt className="eyebrow">API</dt>
                  <dd>
                    <Status tone={data.status === "ok" ? "ok" : "warn"}>
                      {data.status === "ok" ? "Healthy" : "Degraded"} · v{data.version}
                    </Status>
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-4 py-2.5">
                  <dt className="eyebrow">Database</dt>
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
                <div className="flex items-center justify-between gap-4 py-2.5">
                  <dt className="eyebrow">Endpoint</dt>
                  <dd className="truncate font-mono text-[12px] text-ink-3">{API_BASE_URL}</dd>
                </div>
              </dl>
            </Section>
          </div>
        </div>
      )}
    </>
  );
}

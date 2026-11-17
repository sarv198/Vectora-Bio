"use client";

import Link from "next/link";
import { useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DEFAULT_VIEWER, ImageSourceNote, ViewerControls, type ViewerSettings, WellView } from "@/components/CellImages";
import { AgreementMap, FeatureChangeList, PhenotypeMap } from "@/components/PhenotypeMaps";
import { Checkbox, InfoTip, LoadingState, Metrics, Notice, Section, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours, formatScore } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { PerturbationRef, ProfileOverview, WellImageRef } from "@/lib/types";

const MODALITY_LABELS: Record<string, string> = {
  compound: "Compound",
  crispr: "CRISPR knockout",
  orf: "ORF overexpression",
  sirna: "siRNA knockdown",
};

const MAP_HINT =
  "Each cell summarises the features measured in one compartment with one stain: the root-mean-square change from negative controls, in robust z units. Near 0 means indistinguishable from control.";
const AGREEMENT_HINT =
  "Cosine between the two profiles restricted to the features of each compartment and stain. Shows where two perturbations change cells in the same direction, and where they differ.";
const STRENGTH_HINT =
  "Share of control pseudo-replicates (medians of random negative-control wells) whose profile is weaker than this one. Below 95% the response is hard to tell apart from control variation.";

export function perturbationTitle(overview: ProfileOverview): string {
  if (overview.profile_type === "compound") return overview.name ?? overview.perturbation_id;
  return overview.gene ?? overview.perturbation_id;
}

export function modalityLabel(overview: ProfileOverview): string {
  return MODALITY_LABELS[overview.modality ?? overview.profile_type] ?? overview.modality ?? overview.profile_type;
}

function detailHref(overview: ProfileOverview): string {
  return overview.profile_type === "compound"
    ? `/compounds/${encodeURIComponent(overview.perturbation_id)}`
    : `/genes/${encodeURIComponent(overview.gene ?? overview.perturbation_id)}`;
}

/** "> 99%" style strength: share of control pseudo-replicates with a weaker profile. */
export function strengthText(value: number | null): string {
  if (value === null) return "n/a";
  if (value >= 0.995) return "> 99%";
  return `${Math.floor(value * 100)}%`;
}

function useOverview(ref: PerturbationRef) {
  return useApiQuery(() => api.profileOverview(ref.type, ref.id), [ref.type, ref.id]);
}

function ReplicatePicker({
  wells,
  index,
  onChange,
}: {
  wells: WellImageRef[];
  index: number;
  onChange: (index: number) => void;
}) {
  if (wells.length <= 1) return null;
  return (
    <label className="flex items-center gap-2 text-[12.5px] text-ink-3">
      Replicate
      <Select value={index} onChange={(e) => onChange(Number(e.target.value))} className="h-7 w-auto text-[12.5px]">
        {wells.map((well, i) => (
          <option key={`${well.plate}-${well.well}`} value={i}>
            {well.plate} · {well.well}
          </option>
        ))}
      </Select>
    </label>
  );
}

function PerturbationImages({
  overview,
  settings,
  showControl = true,
  stacked = false,
  header,
}: {
  overview: ProfileOverview;
  settings: ViewerSettings;
  showControl?: boolean;
  /** Control below the perturbation instead of beside it (narrow columns). */
  stacked?: boolean;
  header?: React.ReactNode;
}) {
  const [index, setIndex] = useState(0);
  const pickerRow = (
    <div className="flex min-h-7 flex-wrap items-end justify-between gap-2">
      {header}
      <ReplicatePicker wells={overview.wells} index={index} onChange={setIndex} />
    </div>
  );
  if (!overview.images.available || overview.wells.length === 0) {
    return (
      <div className="space-y-2">
        {pickerRow}
        <Notice>{overview.images.message ?? "No images for this perturbation."}</Notice>
      </div>
    );
  }
  const well = overview.wells[Math.min(index, overview.wells.length - 1)];
  const title = perturbationTitle(overview);
  return (
    <div className="space-y-2">
      {pickerRow}
      <div className={`grid gap-3 ${showControl && !stacked ? "sm:grid-cols-2" : ""}`}>
        <WellView
          plate={well.plate}
          well={well.well}
          reference={well.control_well}
          settings={settings}
          caption={title}
          sublabel={`${well.plate} · ${well.well} · field ${settings.field}`}
        />
        {showControl && well.control_well && (
          <WellView
            plate={well.plate}
            well={well.control_well}
            settings={settings}
            caption={overview.profile_type === "compound" ? "DMSO control" : "Negative control"}
            sublabel={`${well.plate} · ${well.control_well} · same plate`}
          />
        )}
      </div>
    </div>
  );
}

/** Full visual readout of one perturbation: images vs. control, phenotype map, strongest changes. */
export function PerturbationInspector({
  target,
  title = "Cell images and phenotype",
}: {
  target: PerturbationRef;
  title?: string;
}) {
  const { data, error, loading } = useOverview(target);
  const [settings, setSettings] = useState<ViewerSettings>(DEFAULT_VIEWER);

  if (error) return <ApiErrorNotice error={error} />;
  if (loading || !data) return <LoadingState label="Loading phenotype" />;

  const weak = data.strength_percentile !== null && data.strength_percentile < 0.95;
  return (
    <Section title={title} description={`${modalityLabel(data)} · ${data.cell_line} · ${formatHours(data.timepoint)}`}>
      <div className="space-y-6">
        <Metrics
          items={[
            {
              label: "Response strength",
              value: strengthText(data.strength_percentile),
              detail: weak ? "Close to control variation" : "of controls are weaker",
              tone: weak ? "warn" : "neutral",
              hint: STRENGTH_HINT,
            },
            {
              label: "Replicate agreement",
              value: formatScore(data.replicate_cosine, 2),
              detail: `mean cosine across ${data.n_replicates ?? "?"} wells`,
            },
            { label: "Profile magnitude", value: data.response_norm.toFixed(1), detail: `L2 norm, ${data.n_features} features` },
          ]}
        />
        <div className="space-y-3">
          <ViewerControls settings={settings} onChange={setSettings} />
          <PerturbationImages overview={data} settings={settings} />
        </div>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <div>
            <h3 className="mb-2 flex items-center gap-1.5 text-[13.5px] font-medium text-ink">
              Phenotype map <InfoTip>{MAP_HINT}</InfoTip>
            </h3>
            <PhenotypeMap cells={data.phenotype_map} />
          </div>
          <div>
            <h3 className="mb-1 text-[13.5px] font-medium text-ink">Largest feature changes vs. controls</h3>
            <FeatureChangeList features={data.top_features} />
          </div>
        </div>
        <ImageSourceNote />
      </div>
    </Section>
  );
}

function ColumnHeader({ overview, role }: { overview: ProfileOverview; role: string }) {
  const weak = overview.strength_percentile !== null && overview.strength_percentile < 0.95;
  return (
    <div className="min-w-0">
      <p className="text-[12px] text-ink-3">{role}</p>
      <p className="flex flex-wrap items-baseline gap-x-2">
        <Link href={detailHref(overview)} className="truncate text-[14px] font-semibold text-ink hover:text-accent">
          {perturbationTitle(overview)}
        </Link>
        <span className="text-[12px] text-ink-3">
          {modalityLabel(overview)} · strength{" "}
          <span className={weak ? "text-warn" : ""}>{strengthText(overview.strength_percentile)}</span>
        </span>
      </p>
    </div>
  );
}

/**
 * Side-by-side visual comparison of two perturbations: images (optionally with same-plate
 * controls), both phenotype maps, and where the two profiles agree or oppose.
 */
export function ComparisonPanel({
  first,
  second,
  firstRole,
  secondRole,
  mode = "similarity",
  title,
}: {
  first: PerturbationRef;
  second: PerturbationRef;
  firstRole: string;
  secondRole: string;
  mode?: "similarity" | "reversal";
  title?: string;
}) {
  const a = useOverview(first);
  const b = useOverview(second);
  const comparison = useApiQuery(
    () =>
      api.compareProfiles({
        first_type: first.type,
        first_id: first.id,
        second_type: second.type,
        second_id: second.id,
        subtract_controls: mode === "reversal",
      }),
    [first.type, first.id, second.type, second.id, mode],
  );
  const [settings, setSettings] = useState<ViewerSettings>(DEFAULT_VIEWER);
  const [showControls, setShowControls] = useState(mode === "reversal");

  const error = a.error ?? b.error ?? comparison.error;
  if (error) return <ApiErrorNotice error={error} />;
  if (!a.data || !b.data) return <LoadingState label="Loading profiles" />;

  const cosine = comparison.data?.cosine;
  const headline =
    cosine === undefined
      ? null
      : mode === "reversal"
        ? `Reversal score ${formatScore(-cosine, 2)}`
        : `Overall cosine ${formatScore(cosine, 2)}`;

  return (
    <Section
      title={title ?? `${perturbationTitle(a.data)} compared with ${perturbationTitle(b.data)}`}
      description={
        mode === "reversal"
          ? "Images of both perturbations with their controls, and where the compound pushes features back."
          : "Cells from both perturbations on the same display scale, and where their profiles agree."
      }
      actions={headline && <span className="tabular text-[13px] font-medium text-ink">{headline}</span>}
    >
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-y border-line py-2">
          <ViewerControls settings={settings} onChange={setSettings} />
          <Checkbox label="Show same-plate controls" checked={showControls} onChange={(e) => setShowControls(e.target.checked)} />
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {[
            { overview: a.data, role: firstRole },
            { overview: b.data, role: secondRole },
          ].map(({ overview, role }) => (
            <PerturbationImages
              key={`${role}-${overview.perturbation_id}`}
              overview={overview}
              settings={settings}
              showControl={showControls}
              stacked
              header={<ColumnHeader overview={overview} role={role} />}
            />
          ))}
        </div>
        <div className="grid gap-8 lg:grid-cols-3">
          <div>
            <h3 className="mb-2 flex items-center gap-1.5 text-[13.5px] font-medium text-ink">
              {perturbationTitle(a.data)} <InfoTip>{MAP_HINT}</InfoTip>
            </h3>
            <PhenotypeMap cells={a.data.phenotype_map} />
          </div>
          <div>
            <h3 className="mb-2 text-[13.5px] font-medium text-ink">{perturbationTitle(b.data)}</h3>
            <PhenotypeMap cells={b.data.phenotype_map} />
          </div>
          {comparison.data && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-[13.5px] font-medium text-ink">
                {mode === "reversal" ? "Where the compound reverses the change" : "Where the profiles agree"}
                <InfoTip>{AGREEMENT_HINT}</InfoTip>
              </h3>
              <AgreementMap cells={comparison.data.cells} opposition={mode === "reversal"} />
            </div>
          )}
        </div>
        <ImageSourceNote />
      </div>
    </Section>
  );
}

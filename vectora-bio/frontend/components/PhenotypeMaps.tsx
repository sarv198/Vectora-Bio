"use client";

import { useState } from "react";

import type { FeatureChange, MapAgreement, PhenotypeMapCell } from "@/lib/types";

const COMPARTMENTS = ["Cell", "Cytoplasm", "Nucleus"];
const COLUMNS: { key: string; label: string; title: string }[] = [
  { key: "DNA", label: "DNA", title: "Hoechst: nuclei" },
  { key: "RNA", label: "RNA", title: "SYTO 14: nucleoli and RNA" },
  { key: "ER", label: "ER", title: "Endoplasmic reticulum" },
  { key: "AGP", label: "AGP", title: "Actin, Golgi, plasma membrane" },
  { key: "Mito", label: "Mito", title: "Mitochondria" },
  { key: "Brightfield", label: "BF", title: "Brightfield" },
  { key: "Shape", label: "Shape", title: "Size, shape and neighbour features (no stain)" },
];

/**
 * Upper bin edges for the RMS robust z (0 = identical to controls). Doubling bins keep weak
 * genetic phenotypes (about 1) and strong compound phenotypes (above 10) on one readable scale.
 */
const HEAT_EDGES = [0.5, 1, 2, 4, 8];
const HEAT_LABELS = ["<0.5", "0.5", "1", "2", "4", ">8"];
function heatStep(value: number): number {
  const index = HEAT_EDGES.findIndex((edge) => value < edge);
  return index === -1 ? HEAT_EDGES.length : index;
}

/** Cosine bins: strongly opposite, opposite, unrelated, same, strongly same. */
const DIV_STEPS = [
  { max: -0.5, color: "var(--div-neg-2)", ink: "#ffffff", label: "< -0.5" },
  { max: -0.2, color: "var(--div-neg-1)", ink: "var(--ink)", label: "-0.5" },
  { max: 0.2, color: "var(--div-mid)", ink: "var(--ink-2)", label: "0" },
  { max: 0.5, color: "var(--div-pos-1)", ink: "var(--ink)", label: "0.5" },
  { max: Infinity, color: "var(--div-pos-2)", ink: "#ffffff", label: "> 0.5" },
];
function divStep(value: number) {
  return DIV_STEPS.find((step) => value < step.max) ?? DIV_STEPS[DIV_STEPS.length - 1];
}

function Grid<T extends { compartment: string; channel: string }>({
  cells,
  render,
  describe,
  label,
}: {
  cells: T[];
  render: (cell: T) => { background: string; color: string; text: string };
  describe: (cell: T) => string;
  label: string;
}) {
  const [hovered, setHovered] = useState<T | null>(null);
  const lookup = new Map(cells.map((cell) => [`${cell.compartment}|${cell.channel}`, cell]));
  const columns = COLUMNS.filter((column) => cells.some((cell) => cell.channel === column.key));

  return (
    <div>
      <table className="w-full table-fixed border-separate border-spacing-[2px] text-[11.5px]" aria-label={label}>
        <thead>
          <tr>
            <th className="w-[4.5rem]" />
            {columns.map((column) => (
              <th key={column.key} title={column.title} className="pb-0.5 text-center font-normal text-ink-3">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COMPARTMENTS.map((compartment) => (
            <tr key={compartment}>
              <th scope="row" className="pr-2 text-left font-normal text-ink-2">
                {compartment}
              </th>
              {columns.map((column) => {
                const cell = lookup.get(`${compartment}|${column.key}`);
                if (!cell) return <td key={column.key} className="rounded-[2px] bg-surface-2" />;
                const style = render(cell);
                return (
                  <td
                    key={column.key}
                    className="h-8 cursor-default rounded-[2px] p-0 text-center"
                    style={{ background: style.background }}
                    onMouseEnter={() => setHovered(cell)}
                    onMouseLeave={() => setHovered(null)}
                    title={describe(cell)}
                  >
                    <span className="tabular" style={{ color: style.color }}>
                      {style.text}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1.5 min-h-[2.6em] text-[12px] leading-snug text-ink-2" aria-live="polite">
        {hovered ? describe(hovered) : <span className="text-ink-3">Hover a cell to see its strongest feature.</span>}
      </p>
    </div>
  );
}

function Legend({ label, steps }: { label: string; steps: { color: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-[11px] text-ink-3">
      <span className="mr-1">{label}</span>
      {steps.map((step) => (
        <span key={step.label} className="flex flex-col items-center">
          <span className="h-2 w-6 rounded-[1px]" style={{ background: step.color }} />
          <span className="tabular mt-0.5">{step.label}</span>
        </span>
      ))}
    </div>
  );
}

/** Compartment x stain map of how far a profile is from controls (RMS of robust z-scores). */
export function PhenotypeMap({ cells }: { cells: PhenotypeMapCell[] }) {
  if (cells.length === 0) {
    return <p className="text-[12.5px] text-ink-3">Feature names are not in CellProfiler format, so no map is available.</p>;
  }
  return (
    <div className="space-y-1">
      <Grid
        cells={cells}
        label="Change versus controls by compartment and stain"
        render={(cell) => {
          const step = heatStep(cell.rms);
          return {
            background: `var(--heat-${step})`,
            color: step >= 3 ? "var(--heat-ink-strong)" : "var(--ink-2)",
            text: cell.rms.toFixed(1),
          };
        }}
        describe={(cell) =>
          `${cell.compartment}, ${cell.channel}: RMS ${cell.rms.toFixed(2)} across ${cell.n_features} features.` +
          (cell.top_label ? ` Strongest: ${cell.top_label} (${formatZ(cell.top_value)}).` : "")
        }
      />
      <Legend
        label="RMS z vs. control"
        steps={HEAT_LABELS.map((label, index) => ({ color: `var(--heat-${index})`, label }))}
      />
    </div>
  );
}

/** Where two profiles agree (teal) or oppose each other (terracotta): cosine within each cell of the map. */
export function AgreementMap({ cells, opposition = false }: { cells: MapAgreement[]; opposition?: boolean }) {
  if (cells.length === 0) return null;
  return (
    <div className="space-y-1">
      <Grid
        cells={cells}
        label="Agreement by compartment and stain"
        render={(cell) => {
          const step = divStep(cell.cosine);
          return { background: step.color, color: step.ink, text: formatSignedShort(cell.cosine) };
        }}
        describe={(cell) =>
          `${cell.compartment}, ${cell.channel}: cosine ${cell.cosine.toFixed(2)} across ${cell.n_features} features` +
          (opposition
            ? cell.cosine < -0.2
              ? ", reversed by the compound."
              : cell.cosine > 0.2
                ? ", made worse by the compound."
                : ", largely unaffected."
            : ".")
        }
      />
      <Legend label={opposition ? "Cosine (negative = reversed)" : "Cosine"} steps={DIV_STEPS} />
    </div>
  );
}

function formatZ(value: number | null): string {
  if (value === null) return "";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)} z`;
}

function formatSignedShort(value: number): string {
  return `${value >= 0 ? "" : "-"}${Math.abs(value).toFixed(2).replace(/^0/, "")}`;
}

/** Strongest single-feature changes as signed bars around zero. */
export function FeatureChangeList({ features, unit = "z" }: { features: FeatureChange[]; unit?: string }) {
  const max = Math.max(...features.map((f) => Math.abs(f.value)), 1e-9);
  return (
    <ul className="divide-y divide-line">
      {features.map((feature) => {
        const width = `${(Math.abs(feature.value) / max) * 50}%`;
        const positive = feature.value >= 0;
        return (
          <li
            key={feature.feature}
            className="grid grid-cols-[minmax(0,1fr)_5rem_4.75rem] items-center gap-3 py-1.5 text-[12.5px]"
          >
            <span className="truncate text-ink-2" title={feature.feature}>
              {feature.label}
            </span>
            <span className="relative h-1.5 rounded-full bg-surface-3" aria-hidden>
              <span className="absolute top-[-2px] bottom-[-2px] left-1/2 w-px bg-line-strong" />
              <span
                className="absolute top-0 bottom-0 rounded-full"
                style={{
                  width,
                  left: positive ? "50%" : undefined,
                  right: positive ? undefined : "50%",
                  background: positive ? "var(--div-pos-2)" : "var(--div-neg-2)",
                }}
              />
            </span>
            <span className="tabular text-right whitespace-nowrap text-ink">
              {positive ? "+" : ""}
              {feature.value.toFixed(1)}
              <span className="text-ink-3"> {unit}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

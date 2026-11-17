"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DEFAULT_VIEWER, ImageSourceNote, ViewerControls, type ViewerSettings, WellView } from "@/components/CellImages";
import { Field, LoadingState, PageHeader, Section, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { PlateLayout, PlateWell } from "@/lib/types";

const ROWS = "ABCDEFGHIJKLMNOP".split("");
const COLS = Array.from({ length: 24 }, (_, i) => i + 1);

/** Categorical slots in fixed order; controls stay neutral. */
const KINDS: Record<string, { label: string; color: string }> = {
  compound: { label: "Compound", color: "var(--series-1)" },
  crispr: { label: "CRISPR guide", color: "var(--series-2)" },
  orf: { label: "ORF", color: "var(--series-3)" },
  control: { label: "Negative control", color: "var(--series-baseline)" },
};

function wellId(row: string, col: number) {
  return `${row}${String(col).padStart(2, "0")}`;
}

function PlateMap({
  layout,
  selected,
  onSelect,
}: {
  layout: PlateLayout;
  selected: string | null;
  onSelect: (well: string) => void;
}) {
  const byWell = useMemo(() => new Map(layout.wells.map((w) => [w.well, w])), [layout]);
  const [hovered, setHovered] = useState<PlateWell | null>(null);
  const kinds = [...new Set(layout.wells.map((w) => w.kind))];
  const focus = hovered ?? byWell.get(selected ?? "") ?? null;

  return (
    <div className="flex flex-wrap items-start gap-x-10 gap-y-4">
      <div className="max-w-full overflow-x-auto">
        <table className="border-collapse text-[10px] text-ink-3" aria-label={`Plate ${layout.plate} layout`}>
          <thead>
            <tr>
              <th />
              {COLS.map((col) => (
                <th key={col} className="h-4 w-[22px] text-center font-normal">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row}>
                <th className="w-4 pr-1.5 text-right font-normal">{row}</th>
                {COLS.map((col) => {
                  const id = wellId(row, col);
                  const well = byWell.get(id);
                  const isSelected = selected === id;
                  return (
                    <td key={col} className="p-[1.5px]">
                      <button
                        type="button"
                        disabled={!well}
                        onClick={() => well && onSelect(id)}
                        onMouseEnter={() => setHovered(well ?? null)}
                        onMouseLeave={() => setHovered(null)}
                        aria-label={well ? `${id}: ${well.label ?? well.kind}` : `${id}: empty`}
                        aria-pressed={isSelected}
                        className={`block h-[19px] w-[19px] rounded-full ${
                          isSelected
                            ? "shadow-[0_0_0_2px_var(--bg),0_0_0_3.5px_var(--ink)]"
                            : "hover:shadow-[0_0_0_2px_var(--bg),0_0_0_3px_var(--ink-3)]"
                        }`}
                        style={{ background: well ? (KINDS[well.kind]?.color ?? "var(--ink-3)") : "var(--surface-3)" }}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="min-w-[13rem] space-y-5 pt-4 text-[12.5px]">
        <ul className="space-y-1.5">
          {kinds.map((kind) => (
            <li key={kind} className="flex items-center gap-2 text-ink-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: KINDS[kind]?.color }} aria-hidden />
              {KINDS[kind]?.label ?? kind}
              <span className="tabular ml-auto pl-4 text-ink-3">{layout.wells.filter((w) => w.kind === kind).length}</span>
            </li>
          ))}
        </ul>
        <div className="min-h-[3.5rem] border-t border-line pt-3" aria-live="polite">
          {focus ? (
            <>
              <p className="text-ink">
                <span className="font-medium">{focus.well}</span> · {focus.label ?? focus.perturbation_id ?? "Unlabelled"}
              </p>
              <p className="text-ink-3">
                {KINDS[focus.kind]?.label ?? focus.kind}
                {focus.perturbation_id ? ` · ${focus.perturbation_id}` : ""}
              </p>
            </>
          ) : (
            <p className="text-ink-3">Hover a well to identify it; click to view its cells.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function WellDetail({ layout, well }: { layout: PlateLayout; well: PlateWell }) {
  const [settings, setSettings] = useState<ViewerSettings>(DEFAULT_VIEWER);
  const controls = layout.wells.filter((w) => w.kind === "control").map((w) => w.well);
  const reference = controls.length ? controls[Math.floor(controls.length / 2)] : null;
  const isControl = well.kind === "control";
  const links: [string, string][] = [];
  if (well.profile_type === "compound" && well.perturbation_id) {
    links.push([`/compounds/${encodeURIComponent(well.perturbation_id)}`, "Compound profile"]);
    links.push([`/similarity?compound=${encodeURIComponent(well.perturbation_id)}`, "Find similar compounds"]);
  }
  if (well.profile_type === "genetic" && well.perturbation_id) {
    if (well.label) links.push([`/genes/${encodeURIComponent(well.label)}`, "Gene profile"]);
    links.push([`/rescue?perturbation=${encodeURIComponent(well.perturbation_id)}`, "Find rescue compounds"]);
  }

  return (
    <Section
      title={`${well.well} · ${well.label ?? well.perturbation_id ?? "Unlabelled"}`}
      description={`${KINDS[well.kind]?.label ?? well.kind}${well.perturbation_id ? ` · ${well.perturbation_id}` : ""}`}
      actions={
        links.length ? (
          <span className="flex flex-wrap gap-4">
            {links.map(([href, label]) => (
              <Link key={href} href={href} className="text-accent hover:underline">
                {label}
              </Link>
            ))}
          </span>
        ) : null
      }
    >
      <div className="space-y-3">
        <div className="border-y border-line py-2">
          <ViewerControls settings={settings} onChange={setSettings} />
        </div>
        <div className={`grid gap-3 ${!isControl && reference ? "sm:grid-cols-2" : "max-w-xl"}`}>
          <WellView
            plate={layout.plate}
            well={well.well}
            reference={reference}
            settings={settings}
            caption={well.label ?? well.well}
            sublabel={`${layout.plate} · ${well.well} · field ${settings.field}`}
          />
          {!isControl && reference && (
            <WellView
              plate={layout.plate}
              well={reference}
              settings={settings}
              caption="Negative control"
              sublabel={`${layout.plate} · ${reference} · same plate`}
            />
          )}
        </div>
        <ImageSourceNote />
      </div>
    </Section>
  );
}

function PlatesView() {
  const router = useRouter();
  const params = useSearchParams();
  const plates = useApiQuery(() => api.listPlates(), []);
  const plate = params.get("plate") ?? plates.data?.[0]?.plate ?? null;
  const layout = useApiQuery(() => (plate ? api.plateLayout(plate) : Promise.resolve(null)), [plate]);
  const [selected, setSelected] = useState<string | null>(params.get("well"));

  useEffect(() => {
    if (layout.data && !layout.data.wells.some((w) => w.well === selected)) {
      setSelected(layout.data.wells.find((w) => w.kind !== "control")?.well ?? null);
    }
  }, [layout.data, selected]);

  const go = (nextPlate: string, well?: string | null) =>
    router.replace(`/plates?plate=${encodeURIComponent(nextPlate)}${well ? `&well=${well}` : ""}`, { scroll: false });

  const selectedWell = layout.data?.wells.find((w) => w.well === selected) ?? null;
  const groups = useMemo(() => {
    const map = new Map<string, NonNullable<typeof plates.data>>();
    for (const p of plates.data ?? []) {
      const key = `${KINDS[p.modality ?? ""]?.label ?? p.modality ?? "Other"} plates`;
      map.set(key, [...(map.get(key) ?? []), p]);
    }
    return [...map.entries()];
  }, [plates.data]);

  return (
    <>
      <PageHeader
        context="Library"
        title="Plates"
        description="The imaged 384-well plates. Select a well to view its Cell Painting field beside a negative control from the same plate."
      />
      {plates.error ? (
        <ApiErrorNotice error={plates.error} />
      ) : !plates.data ? (
        <LoadingState />
      ) : (
        <div className="space-y-9">
          <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
            <Field label="Plate" className="w-64">
              <Select
                value={plate ?? ""}
                onChange={(e) => {
                  setSelected(null);
                  go(e.target.value);
                }}
              >
                {groups.map(([group, items]) => (
                  <optgroup key={group} label={group}>
                    {items.map((p) => (
                      <option key={p.plate} value={p.plate}>
                        {p.plate} · {formatHours(p.timepoint)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </Field>
            {layout.data && (
              <p className="pb-1.5 text-[13px] text-ink-3">
                {layout.data.cell_line} · {formatHours(layout.data.timepoint)} · {layout.data.wells.length} imaged wells
              </p>
            )}
          </div>
          {layout.error ? (
            <ApiErrorNotice error={layout.error} />
          ) : !layout.data ? (
            <LoadingState />
          ) : (
            <>
              <PlateMap
                layout={layout.data}
                selected={selected}
                onSelect={(well) => {
                  setSelected(well);
                  go(layout.data!.plate, well);
                }}
              />
              {selectedWell && (
                <WellDetail key={`${layout.data.plate}-${selectedWell.well}`} layout={layout.data} well={selectedWell} />
              )}
            </>
          )}
        </div>
      )}
    </>
  );
}

export default function PlatesPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <PlatesView />
    </Suspense>
  );
}

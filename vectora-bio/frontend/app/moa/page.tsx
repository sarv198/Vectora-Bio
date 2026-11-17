"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { CompoundPicker } from "@/components/CompoundPicker";
import { MoaResults } from "@/components/MoaResults";
import { Field, LoadingState, Select, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation, useApiQuery } from "@/lib/hooks";

/** Compounds with no MoA on record: the cases inference is actually for. */
function UnannotatedSelect({ onPick }: { onPick: (id: string) => void }) {
  const { data } = useApiQuery(() => api.listCompounds({ annotated: false, limit: 100 }), []);
  const unique = data ? [...new Map(data.items.map((c) => [c.compound_id, c])).values()] : [];
  if (unique.length === 0) return null;
  return (
    <Field label={`Or an unannotated compound (${unique.length})`} className="w-full sm:w-64">
      <Select value="" onChange={(e) => e.target.value && onPick(e.target.value)}>
        <option value="">Choose one</option>
        {unique.map((compound) => (
          <option key={compound.compound_id} value={compound.compound_id}>
            {compound.compound_name}
          </option>
        ))}
      </Select>
    </Field>
  );
}

function MoaView() {
  const router = useRouter();
  const params = useSearchParams();
  const linkedCompound = params.get("compound") ?? "";
  const [compoundId, setCompoundId] = useState(linkedCompound);
  const [pickerKey, setPickerKey] = useState(0);
  const [context, setContext] = useState({ ...DEFAULT_CONTEXT, topK: "5" });
  const [neighbors, setNeighbors] = useState("10");
  const { data, error, loading, run } = useApiMutation(api.inferMoa);

  const submit = (id = compoundId) => {
    if (!id) return;
    router.replace(`/moa?compound=${encodeURIComponent(id)}`, { scroll: false });
    void run({
      compound_id: id,
      cell_line: optionalText(context.cellLine),
      timepoint: optionalNumber(context.timepoint),
      n_neighbors: optionalNumber(neighbors) ?? 10,
      top_k: optionalNumber(context.topK) ?? 5,
    });
  };

  const pick = (id: string) => {
    setCompoundId(id);
    setPickerKey((key) => key + 1); // remount the picker so it shows the chosen compound's name
    submit(id);
  };

  const autoRan = useRef(false);
  useEffect(() => {
    if (linkedCompound && !autoRan.current) {
      autoRan.current = true;
      submit(linkedCompound);
    }
    // Run once for a compound linked via ?compound=.
  }, [linkedCompound]);

  return (
    <AnalysisPage
      title="Mechanism of action"
      description="Estimate a compound's likely mechanism from the annotations of its nearest phenotypic neighbours."
      scoreLabel="Vote share"
      candidateLabel="Mechanism of action"
      submitLabel="Infer mechanism"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() => submit()}
      renderResults={(response) => <MoaResults response={response} />}
      primary={
        <div className="flex flex-wrap items-start gap-3">
          <Field label="Query compound" className="min-w-[240px] flex-1">
            <CompoundPicker key={pickerKey} value={compoundId} onChange={setCompoundId} />
          </Field>
          <UnannotatedSelect onPick={pick} />
        </div>
      }
      parameters={
        <>
          <Field label="Neighbours that vote" hint="Nearest compounds whose labels are counted.">
            <TextInput type="number" min={1} max={100} value={neighbors} onChange={(e) => setNeighbors(e.target.value)} />
          </Field>
          <ContextFields values={context} onChange={setContext} topKLabel="Mechanisms to show" />
        </>
      }
      method={
        <>
          <p>
            Each nearest neighbour with positive similarity votes for its annotated MoA labels, weighted by similarity.
            Vote share is a label&apos;s fraction of the total vote. The query&apos;s own annotation never votes.
          </p>
          <p>
            <strong className="font-medium text-ink">Confidence</strong> is empirical: every annotated compound is hidden
            in turn, its MoA inferred from the rest, and the hit rate at each vote share is fitted by isotonic regression.
            The query is left out of its own calibration.
          </p>
        </>
      }
    />
  );
}

export default function MoaPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <MoaView />
    </Suspense>
  );
}

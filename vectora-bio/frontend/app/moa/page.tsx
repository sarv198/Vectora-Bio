"use client";

import { Network } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { CompoundPicker } from "@/components/CompoundPicker";
import { MoaResults } from "@/components/MoaResults";
import { Field, LoadingState, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation, useApiQuery } from "@/lib/hooks";

function UnannotatedCompounds({ onPick }: { onPick: (id: string) => void }) {
  const { data } = useApiQuery(() => api.listCompounds({ annotated: false, limit: 100 }), []);
  const unique = data ? [...new Map(data.items.map((c) => [c.compound_id, c])).values()] : [];
  if (unique.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-sm font-medium text-ink-2">Unannotated compounds ({unique.length})</p>
      <div className="flex max-h-28 flex-wrap gap-1 overflow-auto">
        {unique.map((compound) => (
          <button
            key={compound.compound_id}
            type="button"
            onClick={() => onPick(compound.compound_id)}
            className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-2 hover:border-accent hover:text-accent"
          >
            {compound.compound_name}
          </button>
        ))}
      </div>
      <p className="mt-1 text-xs text-ink-3">No MoA on record: the cases inference is for.</p>
    </div>
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
      title="Mechanism-of-action inference"
      description="Estimate a compound's likely mechanism from the annotations of its nearest phenotypic neighbours."
      icon={<Network className="h-5 w-5" />}
      scoreLabel="Vote share"
      candidateLabel="Mechanism of action"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() => submit()}
      renderResults={(response) => <MoaResults response={response} />}
      formFields={
        <>
          <Field label="Compound">
            <CompoundPicker key={pickerKey} value={compoundId} onChange={setCompoundId} />
          </Field>
          <UnannotatedCompounds onPick={pick} />
          <Field label="Neighbours" hint="Nearest compounds that vote.">
            <TextInput type="number" min={1} max={100} value={neighbors} onChange={(e) => setNeighbors(e.target.value)} />
          </Field>
          <ContextFields values={context} onChange={setContext} topKLabel="Mechanisms (top k)" />
        </>
      }
      method={
        <>
          <p>
            Each nearest neighbour with positive similarity votes for its annotated MoA labels, weighted by similarity.
            Vote share is a label&apos;s fraction of the total vote.
          </p>
          <p>
            <strong>Confidence</strong> is empirical: every annotated compound is hidden in turn, its MoA inferred from
            the rest, and the hit rate at each vote share is fitted (isotonic regression). The query is left out of its
            own calibration.
          </p>
          <p>The query&apos;s own annotation never votes.</p>
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

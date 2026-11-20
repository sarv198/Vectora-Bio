"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { CompoundPicker } from "@/components/CompoundPicker";
import { MoaResults } from "@/components/MoaResults";
import { Field, LoadingState, Select, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation, useApiQuery } from "@/lib/hooks";
import { readSession, useSessionState } from "@/lib/session";

/** Compounds with no MoA on record: the cases inference is actually for. */
function UnannotatedSelect({ onPick }: { onPick: (id: string) => void }) {
  const { data } = useApiQuery(() => api.listCompounds({ annotated: false, limit: 100 }), []);
  const unique = data ? [...new Map(data.items.map((c) => [c.compound_id, c])).values()] : [];
  if (unique.length === 0) return null;
  return (
    <Field label={`Or an unannotated one (${unique.length})`} className="w-full sm:w-64">
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
  const [compoundId, setCompoundId] = useSessionState("moa.query", linkedCompound);
  const [context, setContext] = useSessionState("moa.context", DEFAULT_CONTEXT);
  const [neighbors, setNeighbors] = useSessionState("moa.neighbors", "10");
  const { data, error, loading, run } = useApiMutation(api.inferMoa, "moa.result");

  const submit = (id = compoundId) => {
    if (!id) return;
    setCompoundId(id);
    router.replace(`/moa?compound=${encodeURIComponent(id)}`, { scroll: false });
    void run({
      compound_id: id,
      cell_line: optionalText(context.cellLine),
      timepoint: optionalNumber(context.timepoint),
      n_neighbors: optionalNumber(neighbors) ?? 10,
      top_k: optionalNumber(context.topK) ?? 5,
    });
  };


  const autoRan = useRef(false);
  useEffect(() => {
    if (linkedCompound && !autoRan.current) {
      autoRan.current = true;
      // Coming back to a result already on screen for this tab should not rerun it.
      if (readSession<{ query_id: string }>("moa.result")?.query_id === linkedCompound) return;
      submit(linkedCompound);
    }
    // Run once for a compound linked via ?compound=.
  }, [linkedCompound]);

  return (
    <AnalysisPage
      title="Mechanism of action"
      description="Estimate a compound's mechanism from its nearest phenotypic neighbours."
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
            <CompoundPicker value={compoundId} onChange={setCompoundId} />
          </Field>
          <UnannotatedSelect onPick={(id) => submit(id)} />
        </div>
      }
      parameters={
        <>
          <Field label="Neighbours that vote">
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

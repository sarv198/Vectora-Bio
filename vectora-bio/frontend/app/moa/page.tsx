"use client";

import { Network } from "lucide-react";
import { useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { Field, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";

export default function MoaPage() {
  const [compoundId, setCompoundId] = useState("");
  const [context, setContext] = useState({ ...DEFAULT_CONTEXT, topK: "5" });
  const [neighbors, setNeighbors] = useState("20");
  const { data, error, loading, run } = useApiMutation(api.inferMoa);

  return (
    <AnalysisPage
      title="Mechanism-of-action inference"
      description="Infer likely mechanisms of action from the annotations of a compound's nearest phenotypic neighbours."
      icon={<Network className="h-5 w-5" />}
      scoreLabel="Vote share"
      candidateLabel="Mechanism of action"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() =>
        run({
          compound_id: compoundId.trim(),
          cell_line: optionalText(context.cellLine),
          timepoint: optionalNumber(context.timepoint),
          n_neighbors: optionalNumber(neighbors) ?? 20,
          top_k: optionalNumber(context.topK) ?? 5,
        })
      }
      formFields={
        <>
          <Field label="Compound id">
            <TextInput required value={compoundId} onChange={(e) => setCompoundId(e.target.value)} />
          </Field>
          <Field label="Neighbours" hint="Nearest compounds that vote.">
            <TextInput type="number" min={1} max={500} value={neighbors} onChange={(e) => setNeighbors(e.target.value)} />
          </Field>
          <ContextFields values={context} onChange={setContext} topKLabel="Mechanisms (top k)" />
        </>
      }
      method={
        <>
          <p>Each of the nearest neighbours with positive similarity votes for its annotated MoA labels, weighted by similarity.</p>
          <p>
            A label&apos;s score is its share of the total vote weight of annotated neighbours (0–1). The query&apos;s own
            annotation is never used.
          </p>
        </>
      }
    />
  );
}

"use client";

import { GitCompareArrows } from "lucide-react";
import { useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { Field, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";

export default function SimilarityPage() {
  const [compoundId, setCompoundId] = useState("");
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const { data, error, loading, run } = useApiMutation(api.similarCompounds);

  return (
    <AnalysisPage
      title="Compound similarity"
      description="Find compounds whose consensus cellular profile most resembles a query compound."
      icon={<GitCompareArrows className="h-5 w-5" />}
      scoreLabel="Cosine similarity"
      candidateLabel="Compound"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() =>
        run({
          compound_id: compoundId.trim(),
          cell_line: optionalText(context.cellLine),
          timepoint: optionalNumber(context.timepoint),
          top_k: optionalNumber(context.topK) ?? 10,
        })
      }
      formFields={
        <>
          <Field label="Compound id">
            <TextInput required value={compoundId} onChange={(e) => setCompoundId(e.target.value)} placeholder="e.g. JCP2022_…" />
          </Field>
          <ContextFields values={context} onChange={setContext} />
        </>
      }
      method={
        <>
          <p>Replicate profiles are aggregated to a per-compound consensus (median by default).</p>
          <p>Candidates are ranked by cosine similarity to the query consensus; the query itself is excluded.</p>
        </>
      }
    />
  );
}

"use client";

import { GitCompareArrows } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { CompoundPicker } from "@/components/CompoundPicker";
import { SimilarityResults } from "@/components/SimilarityResults";
import { Checkbox, Field, LoadingState, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";

function SimilarityView() {
  const router = useRouter();
  const params = useSearchParams();
  const linkedCompound = params.get("compound") ?? "";
  const [compoundId, setCompoundId] = useState(linkedCompound);
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [annotatedOnly, setAnnotatedOnly] = useState(false);
  const [minReplicate, setMinReplicate] = useState("");
  const { data, error, loading, run } = useApiMutation(api.similarCompounds);

  const submit = (id = compoundId) => {
    if (!id) return;
    router.replace(`/similarity?compound=${encodeURIComponent(id)}`, { scroll: false });
    run({
      compound_id: id,
      cell_line: optionalText(context.cellLine),
      timepoint: optionalNumber(context.timepoint),
      top_k: optionalNumber(context.topK) ?? 10,
      annotated_only: annotatedOnly,
      min_replicate_cosine: optionalNumber(minReplicate),
    });
  };

  // Arriving from a compound page (?compound=…) runs the search straight away.
  const autoRan = useRef(false);
  useEffect(() => {
    if (linkedCompound && !autoRan.current) {
      autoRan.current = true;
      submit(linkedCompound);
    }
    // Run once for the linked compound only.
  }, [linkedCompound]);

  return (
    <AnalysisPage
      title="Compound similarity"
      description="Find compounds whose consensus cellular profile most resembles a query compound, alongside their known annotations."
      icon={<GitCompareArrows className="h-5 w-5" />}
      scoreLabel="Cosine similarity"
      candidateLabel="Compound"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() => submit()}
      renderResults={(response) => <SimilarityResults response={response} />}
      formFields={
        <>
          <Field label="Compound">
            <CompoundPicker value={compoundId} onChange={setCompoundId} />
          </Field>
          <ContextFields values={context} onChange={setContext} />
          <Checkbox
            label="Only compounds with a known MoA"
            checked={annotatedOnly}
            onChange={(e) => setAnnotatedOnly(e.target.checked)}
          />
          <Field label="Min. replicate agreement" hint="Optional, −1 to 1. Hides compounds whose replicates disagree.">
            <TextInput
              type="number"
              min={-1}
              max={1}
              step={0.05}
              placeholder="e.g. 0.3"
              value={minReplicate}
              onChange={(e) => setMinReplicate(e.target.value)}
            />
          </Field>
        </>
      }
      method={
        <>
          <p>Each compound is the median of its replicate wells, normalized to DMSO controls on the same plate.</p>
          <p>Candidates are ranked by cosine similarity to the query; the query itself is excluded.</p>
          <p>
            &ldquo;Among all pairs&rdquo; places each score in the distribution of similarities between every pair of
            compounds in the same cell line and timepoint.
          </p>
          <p>Annotations come from imported metadata and never affect the score.</p>
        </>
      }
    />
  );
}

export default function SimilarityPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <SimilarityView />
    </Suspense>
  );
}

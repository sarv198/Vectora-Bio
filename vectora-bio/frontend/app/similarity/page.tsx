"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";

import { AnalysisPage, ContextFields, SHORT_CONTEXT } from "@/components/AnalysisPage";
import { CompoundPicker } from "@/components/CompoundPicker";
import { SimilarityResults } from "@/components/SimilarityResults";
import { Checkbox, Field, LoadingState, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";
import { readSession, useSessionState } from "@/lib/session";

function SimilarityView() {
  const router = useRouter();
  const params = useSearchParams();
  const linkedCompound = params.get("compound") ?? "";
  const [compoundId, setCompoundId] = useSessionState("similarity.query", linkedCompound);
  const [context, setContext] = useSessionState("similarity.context", SHORT_CONTEXT);
  const [annotatedOnly, setAnnotatedOnly] = useSessionState("similarity.annotatedOnly", false);
  const [minReplicate, setMinReplicate] = useSessionState("similarity.minReplicate", "");
  const { data, error, loading, run } = useApiMutation(api.similarCompounds, "similarity.result");

  const submit = (id = compoundId) => {
    if (!id) return;
    setCompoundId(id);
    router.replace(`/similarity?compound=${encodeURIComponent(id)}`, { scroll: false });
    run({
      compound_id: id,
      cell_line: optionalText(context.cellLine),
      timepoint: optionalNumber(context.timepoint),
      top_k: optionalNumber(context.topK) ?? 5,
      annotated_only: annotatedOnly,
      min_replicate_cosine: optionalNumber(minReplicate),
    });
  };

  // Arriving from a compound page (?compound=...) runs the search straight away.
  const autoRan = useRef(false);
  useEffect(() => {
    if (linkedCompound && !autoRan.current) {
      autoRan.current = true;
      // Coming back to a result already on screen for this tab should not rerun it.
      if (readSession<{ query_id: string }>("similarity.result")?.query_id === linkedCompound) return;
      submit(linkedCompound);
    }
    // Run once for the linked compound only.
  }, [linkedCompound]);

  return (
    <AnalysisPage
      title="Compound similarity"
      description="Find compounds that change cells the way a query compound does."
      scoreLabel="Cosine similarity"
      candidateLabel="Compound"
      submitLabel="Find similar"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() => submit()}
      renderResults={(response) => <SimilarityResults response={response} />}
      primary={
        <Field label="Query compound">
          <CompoundPicker value={compoundId} onChange={setCompoundId} />
        </Field>
      }
      parameters={
        <>
          <ContextFields values={context} onChange={setContext} />
          <Field label="Min. replicate agreement" hint="-1 to 1. Hides irreproducible compounds.">
            <TextInput
              type="number"
              min={-1}
              max={1}
              step={0.05}
              placeholder="None"
              value={minReplicate}
              onChange={(e) => setMinReplicate(e.target.value)}
            />
          </Field>
          <Checkbox
            label="Only compounds with a known MoA"
            checked={annotatedOnly}
            onChange={(e) => setAnnotatedOnly(e.target.checked)}
          />
        </>
      }
      method={
        <>
          <p>
            Each compound is the median of its replicate wells, normalised to DMSO controls on the same plate. Candidates
            are ranked by cosine similarity to the query; the query itself is excluded.
          </p>
          <p>
            The percentile places each score among all compound pairs in the same cell line and timepoint, so &ldquo;top
            1%&rdquo; means only 1% of random pairs are this similar. Annotations come from imported metadata and never
            affect the score. Similar cells suggest, but do not prove, a shared mechanism.
          </p>
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

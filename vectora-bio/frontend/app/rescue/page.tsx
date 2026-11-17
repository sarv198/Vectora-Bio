"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { PerturbationPicker } from "@/components/PerturbationPicker";
import { RescueResults } from "@/components/RescueResults";
import { Checkbox, Field, LoadingState, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";

function RescueView() {
  const router = useRouter();
  const params = useSearchParams();
  const linked = params.get("perturbation") ?? "";
  const [perturbationId, setPerturbationId] = useState(linked);
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [subtractControls, setSubtractControls] = useState(true);
  const [excludeWeak, setExcludeWeak] = useState(true);
  const [minStrength, setMinStrength] = useState("95");
  const [excludeStress, setExcludeStress] = useState(false);
  const { data, error, loading, run } = useApiMutation(api.searchRescue);

  const submit = (id = perturbationId) => {
    if (!id) return;
    router.replace(`/rescue?perturbation=${encodeURIComponent(id)}`, { scroll: false });
    void run({
      perturbation_id: id,
      cell_line: optionalText(context.cellLine),
      timepoint: optionalNumber(context.timepoint),
      subtract_matched_controls: subtractControls,
      exclude_weak_responses: excludeWeak,
      min_response_percentile: Math.min(1, Math.max(0, (optionalNumber(minStrength) ?? 95) / 100)),
      exclude_stress_like: excludeStress,
      top_k: optionalNumber(context.topK) ?? 10,
    });
  };

  const autoRan = useRef(false);
  useEffect(() => {
    if (linked && !autoRan.current) {
      autoRan.current = true;
      submit(linked);
    }
    // Run once for a perturbation linked via ?perturbation=.
  }, [linked]);

  return (
    <AnalysisPage
      title="Phenotypic rescue"
      description="Find compounds whose cellular profile opposes the phenotype of a gene knockout or overexpression."
      scoreLabel="Reversal score"
      candidateLabel="Compound"
      submitLabel="Find rescue candidates"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() => submit()}
      renderResults={(response) => <RescueResults response={response} />}
      primary={
        <Field label="Genetic perturbation">
          <PerturbationPicker value={perturbationId} onChange={setPerturbationId} />
        </Field>
      }
      parameters={
        <>
          <ContextFields values={context} onChange={setContext} />
          {excludeWeak && (
            <Field label="Min. response strength (%)" hint="95 = stronger than 95% of control pseudo-replicates.">
              <TextInput type="number" min={0} max={100} value={minStrength} onChange={(e) => setMinStrength(e.target.value)} />
            </Field>
          )}
          <div className="space-y-2">
            <Checkbox
              label="Subtract matched controls"
              checked={subtractControls}
              onChange={(e) => setSubtractControls(e.target.checked)}
            />
            <Checkbox label="Exclude weak responses" checked={excludeWeak} onChange={(e) => setExcludeWeak(e.target.checked)} />
            <Checkbox
              label="Exclude cell-loss and stress-like compounds"
              checked={excludeStress}
              onChange={(e) => setExcludeStress(e.target.checked)}
            />
          </div>
        </>
      }
      method={
        <>
          <p>
            Signature = perturbation profile minus matched controls (same cell line, timepoint and reagent type).
            Compound profiles are control-subtracted the same way. Reversal score = minus the cosine between them: 1 is
            exact opposition, 0 unrelated, -1 mimicry.
          </p>
          <p>
            <strong className="font-medium text-ink">Weak responses</strong> are compounds no stronger than the median of
            4 random DMSO wells. <strong className="font-medium text-ink">Cell loss</strong> uses neighbour and density
            features as a toxicity proxy, since the pilot has no direct cell counts.{" "}
            <strong className="font-medium text-ink">Generic response</strong> marks profiles that resemble many
            unrelated compounds.
          </p>
        </>
      }
    />
  );
}

export default function RescuePage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <RescueView />
    </Suspense>
  );
}

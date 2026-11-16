"use client";

import { Undo2 } from "lucide-react";
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
      description="Find compounds whose cellular profile opposes a genetic perturbation's phenotype, relative to matched controls."
      icon={<Undo2 className="h-5 w-5" />}
      scoreLabel="Reversal score"
      candidateLabel="Compound"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() => submit()}
      renderResults={(response) => <RescueResults response={response} />}
      formFields={
        <>
          <Field label="Genetic perturbation">
            <PerturbationPicker value={perturbationId} onChange={setPerturbationId} />
          </Field>
          <ContextFields values={context} onChange={setContext} />
          <Checkbox
            label="Subtract matched controls"
            checked={subtractControls}
            onChange={(e) => setSubtractControls(e.target.checked)}
          />
          <Checkbox
            label="Exclude weak responses"
            checked={excludeWeak}
            onChange={(e) => setExcludeWeak(e.target.checked)}
          />
          {excludeWeak && (
            <Field label="Min. strength (percentile of controls)" hint="95 = stronger than 95% of DMSO pseudo-replicates.">
              <TextInput type="number" min={0} max={100} value={minStrength} onChange={(e) => setMinStrength(e.target.value)} />
            </Field>
          )}
          <Checkbox
            label="Exclude cell-loss / stress-like compounds"
            checked={excludeStress}
            onChange={(e) => setExcludeStress(e.target.checked)}
          />
        </>
      }
      method={
        <>
          <p>
            Signature = perturbation profile − matched controls (same cell line, timepoint and reagent type). Compound
            profiles are control-subtracted the same way.
          </p>
          <p>Reversal score = −cosine(compound, signature): 1 is exact opposition, 0 unrelated, −1 mimicry.</p>
          <p>
            <strong>Weak responses</strong> are compounds whose profile is no stronger than the median of 4 random DMSO
            wells. <strong>Cell loss</strong> uses neighbour/density features as a toxicity proxy (the pilot has no
            direct cell counts); <strong>generic response</strong> marks profiles that look like many unrelated
            compounds.
          </p>
          <p>Expand a row to see which features drive its score.</p>
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

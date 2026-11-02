"use client";

import { Undo2 } from "lucide-react";
import { useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { Checkbox, Field, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";

export default function RescuePage() {
  const [perturbationId, setPerturbationId] = useState("");
  const [perturbationTimepoint, setPerturbationTimepoint] = useState("");
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [subtractControls, setSubtractControls] = useState(true);
  const { data, error, loading, run } = useApiMutation(api.searchRescue);

  return (
    <AnalysisPage
      title="Phenotypic rescue"
      description="Rank compounds whose profile points opposite a genetic perturbation's phenotype, relative to matched controls."
      icon={<Undo2 className="h-5 w-5" />}
      scoreLabel="Reversal score"
      candidateLabel="Compound"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() =>
        run({
          perturbation_id: perturbationId.trim(),
          perturbation_timepoint: optionalNumber(perturbationTimepoint),
          cell_line: optionalText(context.cellLine),
          timepoint: optionalNumber(context.timepoint),
          subtract_matched_controls: subtractControls,
          top_k: optionalNumber(context.topK) ?? 10,
        })
      }
      formFields={
        <>
          <Field label="Genetic perturbation id">
            <TextInput required value={perturbationId} onChange={(e) => setPerturbationId(e.target.value)} />
          </Field>
          <Field label="Perturbation timepoint (h)" hint="Optional.">
            <TextInput
              type="number"
              min={0}
              step="any"
              value={perturbationTimepoint}
              onChange={(e) => setPerturbationTimepoint(e.target.value)}
            />
          </Field>
          <ContextFields values={context} onChange={setContext} />
          <Checkbox label="Subtract matched controls" checked={subtractControls} onChange={(e) => setSubtractControls(e.target.checked)} />
        </>
      }
      method={
        <>
          <p>
            The perturbation signature is its consensus profile minus the matched control consensus (same cell line and
            timepoint). Compound profiles are control-subtracted the same way.
          </p>
          <p>Reversal score = −cosine(compound, signature): 1 is exact opposition, 0 orthogonal, −1 mimicry.</p>
          <p>Custom feature-vector signatures are supported by the API (POST /api/rescue/search with a signature).</p>
        </>
      }
    />
  );
}

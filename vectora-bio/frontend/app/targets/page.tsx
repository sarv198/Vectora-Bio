"use client";

import { Crosshair } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { CompoundPicker } from "@/components/CompoundPicker";
import { TargetResults } from "@/components/TargetResults";
import { Checkbox, Field, LoadingState, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";
import type { GeneticPerturbationType } from "@/lib/types";

const TYPES: { value: GeneticPerturbationType; label: string }[] = [
  { value: "crispr", label: "CRISPR knockout" },
  { value: "orf", label: "ORF overexpression" },
  { value: "sirna", label: "siRNA" },
];

function TargetsView() {
  const router = useRouter();
  const params = useSearchParams();
  const linkedCompound = params.get("compound") ?? "";
  const [compoundId, setCompoundId] = useState(linkedCompound);
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [geneticTimepoint, setGeneticTimepoint] = useState("");
  const [types, setTypes] = useState<GeneticPerturbationType[]>([]);
  const [absolute, setAbsolute] = useState(true);
  const [neighborWeight, setNeighborWeight] = useState("2");
  const [neighbors, setNeighbors] = useState("10");
  const prioritized = useApiMutation(api.prioritizeTargets);
  const matched = useApiMutation(api.matchGenes);

  const toggleType = (value: GeneticPerturbationType) =>
    setTypes((current) => (current.includes(value) ? current.filter((t) => t !== value) : [...current, value]));

  const submit = (id = compoundId) => {
    if (!id) return;
    router.replace(`/targets?compound=${encodeURIComponent(id)}`, { scroll: false });
    const shared = {
      compound_id: id,
      cell_line: optionalText(context.cellLine),
      timepoint: optionalNumber(context.timepoint),
      genetic_timepoint: optionalNumber(geneticTimepoint),
      perturbation_types: types.length ? types : null,
      use_absolute_similarity: absolute,
      top_k: optionalNumber(context.topK) ?? 10,
    };
    void prioritized.run({
      ...shared,
      neighbor_weight: optionalNumber(neighborWeight) ?? 2,
      n_neighbors: optionalNumber(neighbors) ?? 10,
    });
    void matched.run(shared);
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
      title="Target prioritization"
      description="Which genetic perturbations look like this compound, and which genes have the strongest combined evidence as candidate targets."
      icon={<Crosshair className="h-5 w-5" />}
      scoreLabel="Priority"
      candidateLabel="Gene"
      loading={prioritized.loading || matched.loading}
      error={prioritized.error}
      response={prioritized.data}
      onSubmit={() => submit()}
      renderResults={(response) => (
        <TargetResults prioritized={response} matches={matched.data} matchesError={matched.error} />
      )}
      formFields={
        <>
          <Field label="Compound">
            <CompoundPicker value={compoundId} onChange={setCompoundId} />
          </Field>
          <ContextFields values={context} onChange={setContext} />
          <Field label="Genetic timepoint (h)" hint="Optional. Genetic screens often use a different timepoint.">
            <TextInput
              type="number"
              min={0}
              step="any"
              value={geneticTimepoint}
              onChange={(e) => setGeneticTimepoint(e.target.value)}
            />
          </Field>
          <fieldset className="space-y-1.5">
            <legend className="mb-1 text-sm font-medium text-ink-2">Perturbation types</legend>
            {TYPES.map((type) => (
              <Checkbox
                key={type.value}
                label={type.label}
                checked={types.includes(type.value)}
                onChange={() => toggleType(type.value)}
              />
            ))}
            <p className="text-xs text-ink-3">None selected = all types.</p>
          </fieldset>
          <Checkbox label="Rank by absolute similarity" checked={absolute} onChange={(e) => setAbsolute(e.target.checked)} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Neighbour weight" hint="0 = phenotype only">
              <TextInput type="number" min={0} step={0.5} value={neighborWeight} onChange={(e) => setNeighborWeight(e.target.value)} />
            </Field>
            <Field label="Neighbours">
              <TextInput type="number" min={1} max={100} value={neighbors} onChange={(e) => setNeighbors(e.target.value)} />
            </Field>
          </div>
        </>
      }
      method={
        <>
          <p>
            <strong>Matching:</strong> the compound&apos;s profile is compared with every CRISPR and ORF profile. Each
            cosine is placed among all compound-reagent pairs (&ldquo;Top x%&rdquo;).
          </p>
          <p>
            <strong>Prioritization</strong> combines, per gene, the best reagent&apos;s match percentile with the share
            of the most similar compounds that are annotated to act on that gene.
          </p>
          <p>
            The query&apos;s own annotated targets never enter the score; they are only flagged so you can see where
            they rank. Default weights were chosen on the JUMP pilot and will be validated on held-out compounds in
            Phase 6.
          </p>
        </>
      }
    />
  );
}

export default function TargetsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <TargetsView />
    </Suspense>
  );
}

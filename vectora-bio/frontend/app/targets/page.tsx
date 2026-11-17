"use client";

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
      title="Drug-to-gene matching"
      description="Find genes whose knockout or overexpression changes cells the way a compound does, and rank them as candidate targets."
      scoreLabel="Priority"
      candidateLabel="Gene"
      submitLabel="Match genes"
      loading={prioritized.loading || matched.loading}
      error={prioritized.error}
      response={prioritized.data}
      onSubmit={() => submit()}
      renderResults={(response) => (
        <TargetResults prioritized={response} matches={matched.data} matchesError={matched.error} />
      )}
      primary={
        <Field label="Query compound">
          <CompoundPicker value={compoundId} onChange={setCompoundId} />
        </Field>
      }
      parameters={
        <>
          <Field
            label="Weight of similar compounds"
            hint="0 ranks by phenotype alone, which generalises better to novel chemistry (see Evaluation)."
          >
            <TextInput type="number" min={0} step={0.5} value={neighborWeight} onChange={(e) => setNeighborWeight(e.target.value)} />
          </Field>
          <Field label="Similar compounds considered">
            <TextInput type="number" min={1} max={100} value={neighbors} onChange={(e) => setNeighbors(e.target.value)} />
          </Field>
          <ContextFields values={context} onChange={setContext} />
          <Field label="Genetic timepoint (h)" hint="Genetic screens often use a different timepoint.">
            <TextInput
              type="number"
              min={0}
              step="any"
              placeholder="Any"
              value={geneticTimepoint}
              onChange={(e) => setGeneticTimepoint(e.target.value)}
            />
          </Field>
          <fieldset className="space-y-1.5">
            <legend className="mb-1.5 text-[12.5px] font-medium text-ink-2">Reagent types</legend>
            {TYPES.map((type) => (
              <Checkbox
                key={type.value}
                label={type.label}
                checked={types.includes(type.value)}
                onChange={() => toggleType(type.value)}
              />
            ))}
            <p className="text-[12px] text-ink-3">None selected uses all types.</p>
          </fieldset>
          <Checkbox
            label="Match by absolute similarity"
            hint="Counts strongly opposite profiles as matches too."
            checked={absolute}
            onChange={(e) => setAbsolute(e.target.checked)}
          />
        </>
      }
      method={
        <>
          <p>
            <strong className="font-medium text-ink">Matching.</strong> The compound&apos;s profile is compared with every
            CRISPR and ORF profile. Each cosine is placed among all compound-to-reagent pairs, giving a percentile.
          </p>
          <p>
            <strong className="font-medium text-ink">Prioritisation.</strong> Per gene, the best reagent&apos;s match
            percentile is combined with the share of the most similar compounds annotated to act on that gene:
            priority = (phenotype + w x similar-compound share) / (1 + w).
          </p>
          <p>
            The query&apos;s own annotated targets never enter the score; they are only marked so you can see where they
            rank.
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

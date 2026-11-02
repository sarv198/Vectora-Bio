"use client";

import { Crosshair } from "lucide-react";
import { useState } from "react";

import { AnalysisPage, ContextFields, DEFAULT_CONTEXT } from "@/components/AnalysisPage";
import { Checkbox, Field, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { optionalNumber, optionalText } from "@/lib/format";
import { useApiMutation } from "@/lib/hooks";
import type { GeneticPerturbationType } from "@/lib/types";

const TYPES: { value: GeneticPerturbationType; label: string }[] = [
  { value: "crispr", label: "CRISPR" },
  { value: "orf", label: "ORF" },
  { value: "sirna", label: "siRNA" },
];

export default function TargetsPage() {
  const [compoundId, setCompoundId] = useState("");
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [geneticTimepoint, setGeneticTimepoint] = useState("");
  const [types, setTypes] = useState<GeneticPerturbationType[]>([]);
  const [absolute, setAbsolute] = useState(true);
  const { data, error, loading, run } = useApiMutation(api.prioritizeTargets);

  const toggleType = (value: GeneticPerturbationType) =>
    setTypes((current) => (current.includes(value) ? current.filter((t) => t !== value) : [...current, value]));

  return (
    <AnalysisPage
      title="Target prioritization"
      description="Match a compound's profile against genetic perturbation profiles and rank candidate target genes."
      icon={<Crosshair className="h-5 w-5" />}
      scoreLabel={absolute ? "|Cosine| (max per gene)" : "Cosine (max per gene)"}
      candidateLabel="Gene"
      loading={loading}
      error={error}
      response={data}
      onSubmit={() =>
        run({
          compound_id: compoundId.trim(),
          cell_line: optionalText(context.cellLine),
          timepoint: optionalNumber(context.timepoint),
          genetic_timepoint: optionalNumber(geneticTimepoint),
          perturbation_types: types.length ? types : null,
          use_absolute_similarity: absolute,
          top_k: optionalNumber(context.topK) ?? 10,
        })
      }
      formFields={
        <>
          <Field label="Compound id">
            <TextInput required value={compoundId} onChange={(e) => setCompoundId(e.target.value)} />
          </Field>
          <ContextFields values={context} onChange={setContext} />
          <Field label="Genetic timepoint (h)" hint="Genetic screens often use a different timepoint.">
            <TextInput type="number" min={0} step="any" value={geneticTimepoint} onChange={(e) => setGeneticTimepoint(e.target.value)} />
          </Field>
          <fieldset className="space-y-1.5">
            <legend className="mb-1 text-sm font-medium text-ink-2">Perturbation types</legend>
            {TYPES.map((type) => (
              <Checkbox key={type.value} label={type.label} checked={types.includes(type.value)} onChange={() => toggleType(type.value)} />
            ))}
            <p className="text-xs text-ink-3">None selected = all types.</p>
          </fieldset>
          <Checkbox label="Rank by absolute similarity" checked={absolute} onChange={(e) => setAbsolute(e.target.checked)} />
        </>
      }
      method={
        <>
          <p>The compound consensus profile is compared with every genetic perturbation consensus profile by cosine similarity.</p>
          <p>
            With absolute ranking, anti-correlated perturbations (e.g. overexpression opposing inhibition) are surfaced too; the
            signed value is kept as evidence.
          </p>
          <p>Perturbations are grouped by gene and a gene&apos;s score is its best match. Annotations are shown as evidence only and never change the score.</p>
        </>
      }
    />
  );
}

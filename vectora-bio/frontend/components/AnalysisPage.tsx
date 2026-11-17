"use client";

import { type FormEvent, type ReactNode, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { PredictionResults } from "@/components/PredictionResults";
import { Button, DisclosureButton, EmptyState, Field, LoadingState, PageHeader, Panel, TextInput } from "@/components/ui";
import type { ApiError } from "@/lib/api";
import type { AnalysisResponse } from "@/lib/types";

export interface ContextValues {
  cellLine: string;
  timepoint: string;
  topK: string;
}

export const DEFAULT_CONTEXT: ContextValues = { cellLine: "", timepoint: "", topK: "10" };

/** Cell line / timepoint / result count, shared by every analysis's parameters. */
export function ContextFields({
  values,
  onChange,
  topKLabel = "Results to show",
}: {
  values: ContextValues;
  onChange: (values: ContextValues) => void;
  topKLabel?: string;
}) {
  return (
    <>
      <Field label={topKLabel}>
        <TextInput type="number" min={1} max={500} value={values.topK} onChange={(e) => onChange({ ...values, topK: e.target.value })} />
      </Field>
      <Field label="Cell line" hint="Only needed if profiles span several.">
        <TextInput value={values.cellLine} onChange={(e) => onChange({ ...values, cellLine: e.target.value })} placeholder="Any" />
      </Field>
      <Field label="Timepoint (h)" hint="Only needed if profiles span several.">
        <TextInput
          type="number"
          min={0}
          step="any"
          placeholder="Any"
          value={values.timepoint}
          onChange={(e) => onChange({ ...values, timepoint: e.target.value })}
        />
      </Field>
    </>
  );
}

/**
 * Analytical workspace: a query bar (primary input and run action), optional parameters and
 * method notes behind disclosures, then the results at full width.
 */
export function AnalysisPage({
  title,
  description,
  context = "Analysis",
  primary,
  parameters,
  method,
  submitLabel = "Run analysis",
  onSubmit,
  loading,
  error,
  response,
  scoreLabel,
  candidateLabel,
  renderResults,
  emptyHint,
}: {
  title: string;
  description: ReactNode;
  context?: string;
  primary: ReactNode;
  parameters?: ReactNode;
  method: ReactNode;
  submitLabel?: string;
  onSubmit: () => void;
  loading: boolean;
  error: ApiError | null;
  response: AnalysisResponse | null;
  scoreLabel: string;
  candidateLabel?: string;
  renderResults?: (response: AnalysisResponse) => ReactNode;
  emptyHint?: ReactNode;
}) {
  const [showParameters, setShowParameters] = useState(false);
  const [showMethod, setShowMethod] = useState(false);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <>
      <PageHeader context={context} title={title} description={description} />
      <Panel>
        <form onSubmit={handleSubmit}>
          <div className="flex flex-wrap items-start gap-3 p-4">
            <div className="min-w-[260px] flex-1">{primary}</div>
            {/* Offset by the field label so the button lines up with the input, not its helper text. */}
            <div className="pt-[25px]">
              <Button type="submit" loading={loading} className="min-w-[124px]">
                {submitLabel}
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-5 border-t border-line px-4 py-2.5">
            {parameters && (
              <DisclosureButton open={showParameters} onToggle={() => setShowParameters((v) => !v)}>
                Parameters
              </DisclosureButton>
            )}
            <DisclosureButton open={showMethod} onToggle={() => setShowMethod((v) => !v)}>
              How it works
            </DisclosureButton>
          </div>
          {showParameters && parameters && (
            <div className="grid gap-x-5 gap-y-4 border-t border-line p-4 sm:grid-cols-2 lg:grid-cols-4">{parameters}</div>
          )}
          {showMethod && (
            <div className="max-w-[86ch] space-y-2 border-t border-line p-4 text-[13px] leading-relaxed text-ink-2">{method}</div>
          )}
        </form>
      </Panel>

      <div className="mt-9">
        {error ? (
          <ApiErrorNotice error={error} />
        ) : loading && !response ? (
          <LoadingState label="Running analysis" />
        ) : response ? (
          <div className={loading ? "opacity-60" : ""}>
            {renderResults ? (
              renderResults(response)
            ) : (
              <PredictionResults response={response} scoreLabel={scoreLabel} candidateLabel={candidateLabel} />
            )}
          </div>
        ) : (
          <EmptyState title="No analysis run yet">
            {emptyHint ?? "Choose a query above and run the analysis. Results show the ranked evidence, cell images and phenotype maps."}
          </EmptyState>
        )}
      </div>
    </>
  );
}

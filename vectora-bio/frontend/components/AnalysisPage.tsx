"use client";

import { BookOpen, SlidersHorizontal } from "lucide-react";
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

/** Every analysis lists its top 5 unless more are asked for in Parameters. */
export const DEFAULT_CONTEXT: ContextValues = { cellLine: "", timepoint: "", topK: "5" };

/** Kept for the pages that import it; identical to DEFAULT_CONTEXT. */
export const SHORT_CONTEXT: ContextValues = DEFAULT_CONTEXT;

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
      <Field label="Cell line">
        <TextInput value={values.cellLine} onChange={(e) => onChange({ ...values, cellLine: e.target.value })} placeholder="Any" />
      </Field>
      <Field label="Timepoint (h)">
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
          <div className="flex flex-wrap items-start gap-3 p-5">
            <div className="min-w-[260px] flex-1">{primary}</div>
            {/* Offset by the field label so the button lines up with the input, not its helper text. */}
            <div className="pt-6">
              <Button type="submit" loading={loading} className="min-w-[132px]">
                {submitLabel}
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-7 gap-y-1 border-t border-line px-5 py-1.5">
            {parameters && (
              <DisclosureButton
                icon={SlidersHorizontal}
                open={showParameters}
                onToggle={() => setShowParameters((v) => !v)}
              >
                Parameters
              </DisclosureButton>
            )}
            <DisclosureButton icon={BookOpen} open={showMethod} onToggle={() => setShowMethod((v) => !v)}>
              How it works
            </DisclosureButton>
          </div>
          {showParameters && parameters && (
            <div className="grid gap-x-6 gap-y-5 border-t border-line p-5 sm:grid-cols-2 lg:grid-cols-4">{parameters}</div>
          )}
          {showMethod && (
            <div className="max-w-[86ch] space-y-2 border-t border-line p-5 text-[13.5px] leading-relaxed text-ink-2">{method}</div>
          )}
        </form>
      </Panel>

      <div className="mt-12">
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
            {emptyHint ?? "Choose a query above and run it."}
          </EmptyState>
        )}
      </div>
    </>
  );
}

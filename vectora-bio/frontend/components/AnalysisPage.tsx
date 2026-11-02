"use client";

import type { FormEvent, ReactNode } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { PredictionResults } from "@/components/PredictionResults";
import { Button, Card, EmptyState, Field, PageHeader, TextInput } from "@/components/ui";
import type { ApiError } from "@/lib/api";
import type { AnalysisResponse } from "@/lib/types";

export interface ContextValues {
  cellLine: string;
  timepoint: string;
  topK: string;
}

export const DEFAULT_CONTEXT: ContextValues = { cellLine: "", timepoint: "", topK: "10" };

/** Cell line / timepoint / top-k inputs shared by every analysis form. */
export function ContextFields({
  values,
  onChange,
  topKLabel = "Results (top k)",
}: {
  values: ContextValues;
  onChange: (values: ContextValues) => void;
  topKLabel?: string;
}) {
  return (
    <>
      <Field label="Cell line" hint="Optional; required if profiles span several.">
        <TextInput value={values.cellLine} onChange={(e) => onChange({ ...values, cellLine: e.target.value })} placeholder="e.g. U2OS" />
      </Field>
      <Field label="Timepoint (h)" hint="Optional.">
        <TextInput
          type="number"
          min={0}
          step="any"
          value={values.timepoint}
          onChange={(e) => onChange({ ...values, timepoint: e.target.value })}
        />
      </Field>
      <Field label={topKLabel}>
        <TextInput type="number" min={1} max={500} value={values.topK} onChange={(e) => onChange({ ...values, topK: e.target.value })} />
      </Field>
    </>
  );
}

/** Shared layout: header, query form, then error / empty / results. */
export function AnalysisPage({
  title,
  description,
  icon,
  formFields,
  onSubmit,
  loading,
  error,
  response,
  scoreLabel,
  candidateLabel,
  method,
}: {
  title: string;
  description: ReactNode;
  icon: ReactNode;
  formFields: ReactNode;
  onSubmit: () => void;
  loading: boolean;
  error: ApiError | null;
  response: AnalysisResponse | null;
  scoreLabel: string;
  candidateLabel?: string;
  method: ReactNode;
}) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <>
      <PageHeader title={title} description={description} icon={icon} />
      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Query">
            <form onSubmit={handleSubmit} className="space-y-3">
              {formFields}
              <Button type="submit" loading={loading} className="w-full">
                Run analysis
              </Button>
            </form>
          </Card>
          <Card title="Method">
            <div className="space-y-2 text-xs leading-relaxed text-ink-2">{method}</div>
          </Card>
        </div>
        <div className="min-w-0">
          {error ? (
            <ApiErrorNotice error={error} />
          ) : response ? (
            <PredictionResults response={response} scoreLabel={scoreLabel} candidateLabel={candidateLabel} />
          ) : (
            <EmptyState title="No query yet">Fill in the query and run the analysis.</EmptyState>
          )}
        </div>
      </div>
    </>
  );
}

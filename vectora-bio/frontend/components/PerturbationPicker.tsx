"use client";

import { Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { GeneticPerturbation } from "@/lib/types";

const DEBOUNCE_MS = 200;

/** Search genes by symbol and pick one genetic reagent (CRISPR guide or ORF). `value` is its perturbation id. */
export function PerturbationPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [text, setText] = useState(value);
  const [selected, setSelected] = useState<GeneticPerturbation | null>(null);
  const [options, setOptions] = useState<GeneticPerturbation[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const query = text.trim();
    if (!open || query.length < 2 || (selected && query === selected.gene_symbol)) {
      setOptions([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .listGenes({ search: query, limit: 20 })
        .then((page) => {
          if (!cancelled) {
            setOptions(page.items);
            setActive(0);
          }
        })
        .catch(() => !cancelled && setOptions([]));
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [text, open, selected]);

  const choose = (item: GeneticPerturbation) => {
    setSelected(item);
    setText(item.gene_symbol);
    onChange(item.perturbation_id);
    setOpen(false);
  };

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-ink-3" aria-hidden />
      <input
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        required
        value={text}
        placeholder="Gene symbol (e.g. CDK2) or reagent id"
        onChange={(event) => {
          setText(event.target.value);
          setSelected(null);
          onChange(event.target.value.trim());
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          blurTimer.current = setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={(event) => {
          if (!open || options.length === 0) return;
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((index) => (index + 1) % options.length);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((index) => (index - 1 + options.length) % options.length);
          } else if (event.key === "Enter") {
            event.preventDefault();
            choose(options[active]);
          } else if (event.key === "Escape") {
            setOpen(false);
          }
        }}
        className="w-full rounded-md border border-line bg-surface py-1.5 pr-3 pl-8 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none"
      />
      {selected && (
        <p className="mt-1 truncate text-[11px] text-ink-3">
          {selected.perturbation_type.toUpperCase()} · <span className="font-mono">{selected.perturbation_id}</span> ·{" "}
          {selected.timepoint} h
        </p>
      )}
      {open && options.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-line bg-surface py-1 shadow-lg"
          onMouseDown={() => blurTimer.current && clearTimeout(blurTimer.current)}
        >
          {options.map((item, index) => (
            <li
              key={`${item.perturbation_id}-${item.timepoint}`}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onMouseDown={(event) => {
                event.preventDefault();
                choose(item);
              }}
              className={`cursor-pointer px-3 py-1.5 text-sm ${index === active ? "bg-accent-soft" : ""}`}
            >
              <p className="font-medium">
                {item.gene_symbol}{" "}
                <span className="text-xs font-normal text-ink-3">
                  {item.perturbation_type === "crispr" ? "CRISPR knockout" : item.perturbation_type === "orf" ? "ORF overexpression" : item.perturbation_type.toUpperCase()}
                </span>
              </p>
              <p className="truncate font-mono text-[11px] text-ink-3">{item.perturbation_id}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

import { Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Compound } from "@/lib/types";

const DEBOUNCE_MS = 200;
const MAX_OPTIONS = 8;

/**
 * Search compounds by name or id and pick one. `value` is the compound id sent to the API;
 * typing an id directly also works when the search has no match.
 */
export function CompoundPicker({
  value,
  onChange,
  inputId,
}: {
  value: string;
  onChange: (compoundId: string) => void;
  inputId?: string;
}) {
  const [text, setText] = useState(value);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [options, setOptions] = useState<Compound[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // The last id this picker reported, to tell its own edits from a value set from outside.
  const emitted = useRef<string | null>(null);

  // An id set from outside (a link, a restored session) shows the compound's name once known.
  useEffect(() => {
    if (value === emitted.current) return;
    setText(value);
    setSelectedName(null);
    if (!value) return;
    let cancelled = false;
    api
      .getCompound(value)
      .then((compound) => {
        if (!cancelled && compound.compound_name !== value) {
          setSelectedName(compound.compound_name);
          setText(compound.compound_name);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [value]);

  useEffect(() => {
    const query = text.trim();
    if (!open || query.length < 2 || query === selectedName) {
      setOptions([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .listCompounds({ search: query, limit: 50 })
        .then((page) => {
          if (cancelled) return;
          const unique = new Map<string, Compound>();
          for (const compound of page.items) {
            if (!unique.has(compound.compound_id)) unique.set(compound.compound_id, compound);
          }
          setOptions([...unique.values()].slice(0, MAX_OPTIONS));
          setActive(0);
        })
        .catch(() => !cancelled && setOptions([]));
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [text, open, selectedName]);

  const choose = (compound: Compound) => {
    setText(compound.compound_name);
    setSelectedName(compound.compound_name);
    emitted.current = compound.compound_id;
    onChange(compound.compound_id);
    setOpen(false);
  };

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-ink-3" strokeWidth={1.75} aria-hidden />
      <input
        id={inputId}
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        required
        value={text}
        placeholder="Search by name or id"
        onChange={(event) => {
          setText(event.target.value);
          setSelectedName(null);
          emitted.current = event.target.value.trim();
          onChange(emitted.current);
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
        className="h-8 w-full rounded-md border border-line-strong bg-surface pr-3 pl-8 text-[13.5px] text-ink placeholder:text-ink-3 hover:border-ink-3 focus:border-accent focus:shadow-[0_0_0_3px_var(--focus)] focus:outline-none"
      />
      {selectedName && value && <p className="mt-1 truncate font-mono text-[11.5px] text-ink-3">{value}</p>}
      {open && options.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-80 w-full overflow-auto rounded-md border border-line bg-surface py-1 shadow-[0_6px_20px_rgba(0,0,0,0.08)]"
          onMouseDown={() => blurTimer.current && clearTimeout(blurTimer.current)}
        >
          {options.map((compound, index) => (
            <li
              key={compound.compound_id}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onMouseDown={(event) => {
                event.preventDefault();
                choose(compound);
              }}
              className={`cursor-pointer px-3 py-1.5 text-[13.5px] ${index === active ? "bg-surface-2" : ""}`}
            >
              <p className="truncate text-ink">{compound.compound_name}</p>
              <p className="truncate text-xs text-ink-3">
                <span className="font-mono">{compound.compound_id}</span>
                {compound.moa ? ` · ${compound.moa}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

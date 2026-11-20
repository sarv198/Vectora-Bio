"use client";

import { useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";
export const THEME_STORAGE_KEY = "cellscope-theme";

/** Runs before first paint (inlined in <head>) so the stored theme never flashes. */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t;}}catch(e){}})();`;

function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  try {
    if (choice === "system") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // Storage blocked: the choice still applies for this page view.
  }
}

const OPTIONS: { value: ThemeChoice; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Auto" },
];

/** Light / dark / system switch, drawn as small text options on the sidebar. */
export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>("system");

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    setChoice(current === "light" || current === "dark" ? current : "system");
  }, []);

  return (
    <div role="radiogroup" aria-label="Colour theme" className="flex items-center gap-3">
      {OPTIONS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={choice === value}
          title={value === "system" ? "Follow the system theme" : `${label} theme`}
          onClick={() => {
            setChoice(value);
            apply(value);
          }}
          className={`border-b pb-0.5 font-mono text-[10.5px] tracking-[0.08em] uppercase ${
            choice === value
              ? "border-sidebar-accent text-sidebar-ink"
              : "border-transparent text-sidebar-ink-2 hover:text-sidebar-ink"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

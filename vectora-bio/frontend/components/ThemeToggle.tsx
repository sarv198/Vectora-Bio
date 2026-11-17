"use client";

import { Monitor, Moon, Sun } from "lucide-react";
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

const OPTIONS: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

/** Light / dark / system switch. */
export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>("system");

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    setChoice(current === "light" || current === "dark" ? current : "system");
  }, []);

  return (
    <div role="radiogroup" aria-label="Colour theme" className="inline-flex rounded-md bg-surface-3 p-0.5">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={choice === value}
          title={`${label} theme`}
          onClick={() => {
            setChoice(value);
            apply(value);
          }}
          className={`flex h-6 w-7 items-center justify-center rounded-[3px] ${
            choice === value ? "bg-surface text-ink shadow-[0_1px_1px_rgba(0,0,0,0.06)]" : "text-ink-3 hover:text-ink"
          }`}
        >
          <Icon className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}

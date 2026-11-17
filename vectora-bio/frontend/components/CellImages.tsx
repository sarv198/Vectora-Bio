"use client";

import { ImageOff, Loader2, Maximize2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Segmented, Select } from "@/components/ui";
import { wellImageUrl } from "@/lib/api";

/** Stain channels in display order, with the pseudo-colours the backend blends them in. */
export const CHANNELS: { key: string; short: string; stain: string; color: string }[] = [
  { key: "DNA", short: "DNA", stain: "Hoechst: nuclei", color: "#3373ff" },
  { key: "ER", short: "ER", stain: "Concanavalin A: endoplasmic reticulum", color: "#1af240" },
  { key: "RNA", short: "RNA", stain: "SYTO 14: nucleoli and cytoplasmic RNA", color: "#ffcc0d" },
  { key: "AGP", short: "AGP", stain: "Phalloidin and WGA: actin, Golgi, plasma membrane", color: "#ff33d9" },
  { key: "Mito", short: "Mito", stain: "MitoTracker: mitochondria", color: "#ff2e14" },
  { key: "Brightfield", short: "BF", stain: "Brightfield", color: "#ffffff" },
];

export const FIELD_COUNT = 9;
const PIXEL_SIZE_UM = 0.598;
const IMAGE_SIZE_PX = 1080;
const SCALE_BAR_UM = 100;

export interface ViewerSettings {
  field: number;
  channels: string[];
  mode: "composite" | "split";
}

export const DEFAULT_VIEWER: ViewerSettings = { field: 5, channels: ["DNA", "ER", "Mito"], mode: "composite" };

/** Stain channels, field of view and display mode, shared by every image in a view. */
export function ViewerControls({
  settings,
  onChange,
}: {
  settings: ViewerSettings;
  onChange: (settings: ViewerSettings) => void;
}) {
  const toggle = (key: string) => {
    const has = settings.channels.includes(key);
    const next = has ? settings.channels.filter((c) => c !== key) : [...settings.channels, key];
    if (next.length) onChange({ ...settings, channels: CHANNELS.map((c) => c.key).filter((c) => next.includes(c)) });
  };
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Stain channels">
        {CHANNELS.map((channel) => {
          const on = settings.channels.includes(channel.key);
          return (
            <button
              key={channel.key}
              type="button"
              aria-pressed={on}
              title={channel.stain}
              onClick={() => toggle(channel.key)}
              className={`flex h-7 items-center gap-1.5 rounded-md border px-2 text-[12.5px] ${
                on ? "border-line-strong bg-surface text-ink" : "border-transparent text-ink-3 hover:text-ink"
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  background: on ? channel.color : "transparent",
                  boxShadow: `inset 0 0 0 1px ${channel.key === "Brightfield" ? "var(--ink-3)" : channel.color}`,
                }}
                aria-hidden
              />
              {channel.short}
            </button>
          );
        })}
      </div>
      <label className="flex items-center gap-2 text-[12.5px] text-ink-3">
        Field
        <Select
          value={settings.field}
          onChange={(e) => onChange({ ...settings, field: Number(e.target.value) })}
          className="h-7 w-[4.5rem] text-[12.5px]"
        >
          {Array.from({ length: FIELD_COUNT }, (_, i) => i + 1).map((field) => (
            <option key={field} value={field}>
              {field} of {FIELD_COUNT}
            </option>
          ))}
        </Select>
      </label>
      <Segmented
        label="Display mode"
        value={settings.mode}
        onChange={(mode) => onChange({ ...settings, mode })}
        options={[
          { value: "composite", label: "Composite" },
          { value: "split", label: "Channels" },
        ]}
      />
    </div>
  );
}

type LoadState = "loading" | "loaded" | "error";

/** One microscopy field in a dark viewer frame, with label, scale bar and full-resolution link. */
export function CellImage({
  plate,
  well,
  field,
  channels,
  reference,
  caption,
  sublabel,
  size = 540,
  grayscale = false,
  compact = false,
}: {
  plate: string;
  well: string;
  field: number;
  channels: string[];
  reference?: string | null;
  caption: string;
  sublabel?: string;
  size?: number;
  grayscale?: boolean;
  compact?: boolean;
}) {
  const src = wellImageUrl({ plate, well, field, channels, size, ref: reference, grayscale });
  const [state, setState] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setState("loading");
    setMessage(null);
  }, [src]);

  const onError = () => {
    setState("error");
    fetch(src)
      .then((response) => response.json())
      .then((body: { message?: string }) => setMessage(body.message ?? null))
      .catch(() => setMessage("The API could not be reached."));
  };

  return (
    <figure className="min-w-0">
      <div className="group relative aspect-square w-full overflow-hidden rounded-md bg-viewer">
        {/* eslint-disable-next-line @next/next/no-img-element -- rendered by the API, not a static asset */}
        <img
          key={src}
          src={src}
          alt={`${caption}: ${grayscale ? channels[0] : channels.join(" + ")}, plate ${plate} well ${well} field ${field}`}
          className={`h-full w-full object-contain ${state === "loaded" ? "" : "invisible"}`}
          onLoad={() => setState("loaded")}
          onError={onError}
        />
        {state === "loading" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-[12px] text-white/55">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            {!compact && <span>Loading field from the Cell Painting Gallery</span>}
          </div>
        )}
        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-[12px] text-white/70">
            <ImageOff className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            <span>{message ?? "Image unavailable."}</span>
          </div>
        )}
        <span className="pointer-events-none absolute top-2 left-2 text-[11.5px] font-medium text-white/90 [text-shadow:0_1px_2px_rgba(0,0,0,0.8)]">
          {caption}
        </span>
        {state === "loaded" && (
          <>
            <div className="pointer-events-none absolute right-2.5 bottom-2.5 flex flex-col items-end gap-1">
              <span className="text-[10.5px] text-white/85 [text-shadow:0_1px_2px_rgba(0,0,0,0.8)]">{SCALE_BAR_UM} µm</span>
              <span
                className="block h-[2px] bg-white/90"
                style={{ width: `${(SCALE_BAR_UM / (IMAGE_SIZE_PX * PIXEL_SIZE_UM)) * 100}%`, minWidth: 16 }}
              />
            </div>
            {!compact && (
              <a
                href={wellImageUrl({ plate, well, field, channels, size: 1080, ref: reference, grayscale })}
                target="_blank"
                rel="noreferrer"
                title="Open at full resolution (1080 px)"
                className="absolute top-1.5 right-1.5 rounded p-1 text-white/0 group-hover:bg-black/50 group-hover:text-white/85 focus-visible:text-white/85"
              >
                <Maximize2 className="h-3.5 w-3.5" aria-hidden />
                <span className="sr-only">Open full resolution</span>
              </a>
            )}
          </>
        )}
      </div>
      {sublabel && <figcaption className="mt-1.5 truncate text-[12px] text-ink-3">{sublabel}</figcaption>}
    </figure>
  );
}

/** A well rendered according to the viewer settings: one composite, or one grayscale tile per channel. */
export function WellView({
  plate,
  well,
  reference,
  settings,
  caption,
  sublabel,
}: {
  plate: string;
  well: string;
  reference?: string | null;
  settings: ViewerSettings;
  caption: string;
  sublabel?: string;
}) {
  if (settings.mode === "composite") {
    return (
      <CellImage
        plate={plate}
        well={well}
        field={settings.field}
        channels={settings.channels}
        reference={reference}
        caption={caption}
        sublabel={sublabel}
      />
    );
  }
  return (
    <div className="min-w-0">
      <div className="grid grid-cols-3 gap-1">
        {settings.channels.map((channel) => (
          <CellImage
            key={channel}
            plate={plate}
            well={well}
            field={settings.field}
            channels={[channel]}
            reference={reference}
            caption={channel}
            size={360}
            grayscale
            compact
          />
        ))}
      </div>
      {sublabel && <p className="mt-1.5 truncate text-[12px] text-ink-3">{sublabel}</p>}
    </div>
  );
}

export function ImageSourceNote() {
  return (
    <p className="max-w-[90ch] text-[12px] leading-relaxed text-ink-3">
      Raw fields from the JUMP Cell Painting pilot (CPJUMP1, U2OS, 20x, 0.6 µm per pixel), loaded on first view and
      cached locally. Each image uses the display range of a negative-control well on the same plate, so brightness
      differences are real. Background is set per image.
    </p>
  );
}

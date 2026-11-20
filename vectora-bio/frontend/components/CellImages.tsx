"use client";

import { Clock, ImageOff, Loader2, Maximize2 } from "lucide-react";
import { useEffect, useState } from "react";

import { InfoTip, MetaLine, Segmented, Select } from "@/components/ui";
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

/** Size of the per-stain tiles in the Channels view (the API pre-renders tiles at this size). */
export const CHANNEL_TILE_SIZE = 360;

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
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1" role="group" aria-label="Stain channels">
        {CHANNELS.map((channel) => {
          const on = settings.channels.includes(channel.key);
          return (
            <button
              key={channel.key}
              type="button"
              aria-pressed={on}
              title={channel.stain}
              onClick={() => toggle(channel.key)}
              className={`flex h-7 items-center gap-1.5 border-b text-[12.5px] ${
                on ? "border-ink text-ink" : "border-transparent text-ink-3 hover:text-ink"
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
      <label className="eyebrow flex items-center gap-2">
        Field
        <Select
          value={settings.field}
          onChange={(e) => onChange({ ...settings, field: Number(e.target.value) })}
          className="h-8 w-[5rem] text-[12.5px] tracking-normal normal-case"
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
          { value: "split", label: "Channels", title: "One image per stain. Slower to load the first time." },
        ]}
      />
      {settings.mode === "split" && (
        <p className="flex items-center gap-1.5 text-[12px] text-ink-3" role="note">
          <Clock className="h-3.5 w-3.5 shrink-0 text-warn" strokeWidth={1.9} aria-hidden />
          One image per stain: the first view can take up to a minute.
        </p>
      )}
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
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    setState("loading");
    setMessage(null);
    setSlow(false);
    const timer = window.setTimeout(() => setSlow(true), 8000);
    return () => window.clearTimeout(timer);
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
      <div className="group scanlines relative aspect-square w-full overflow-hidden bg-viewer">
        {/* eslint-disable-next-line @next/next/no-img-element -- rendered by the API, not a static asset */}
        <img
          key={src}
          src={src}
          alt={`${caption}: ${grayscale ? channels[0] : channels.join(" + ")}, plate ${plate} well ${well} field ${field}`}
          loading="lazy"
          decoding="async"
          className={`h-full w-full object-contain ${state === "loaded" ? "" : "invisible"}`}
          onLoad={() => setState("loaded")}
          onError={onError}
        />
        {state === "loading" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center text-[12px] text-white/60">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            {!compact && (
              <span>{slow ? "Still loading: the server fetches each image the first time it is viewed." : "Loading image"}</span>
            )}
          </div>
        )}
        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-[12px] text-white/70">
            <ImageOff className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            <span>{message ?? "Image unavailable."}</span>
          </div>
        )}
        <CornerTicks />
        <span className="pointer-events-none absolute top-2.5 left-3 font-mono text-[10.5px] tracking-[0.06em] text-white/90 uppercase [text-shadow:0_1px_2px_rgba(0,0,0,0.8)]">
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
                className="absolute top-2 right-2 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-white/0 text-white/0 group-hover:border-white/50 group-hover:bg-black/40 group-hover:text-white/90 focus-visible:border-white/50 focus-visible:text-white/90"
              >
                <Maximize2 className="h-3.5 w-3.5" aria-hidden />
                <span className="sr-only">Open full resolution</span>
              </a>
            )}
          </>
        )}
      </div>
      {sublabel && <figcaption className="subline mt-2 truncate">{sublabel}</figcaption>}
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
            size={CHANNEL_TILE_SIZE}
            grayscale
            compact
          />
        ))}
      </div>
      {sublabel && <p className="subline mt-2 truncate">{sublabel}</p>}
    </div>
  );
}

/** Where the images come from, as a small label with the details in a tooltip. */
export function ImageSourceNote() {
  return (
    <p className="flex items-center gap-1.5 whitespace-nowrap">
      <MetaLine items={["CPJUMP1", "U2OS", "20X"]} />
      <InfoTip>
        JUMP Cell Painting pilot. Raw fields (0.6 µm per pixel), loaded on first view and cached. Each image uses the
        display range of a negative-control well on the same plate, so brightness differences are real. Background is
        set per image.
      </InfoTip>
    </p>
  );
}

/** Thin L-shaped ticks in the corners of a microscopy frame, like a viewfinder. */
function CornerTicks() {
  const tick = "pointer-events-none absolute z-[1] h-3 w-3 border-white/45";
  return (
    <>
      <span className={`${tick} top-1.5 left-1.5 border-t border-l`} aria-hidden />
      <span className={`${tick} top-1.5 right-1.5 border-t border-r`} aria-hidden />
      <span className={`${tick} bottom-1.5 left-1.5 border-b border-l`} aria-hidden />
      <span className={`${tick} right-1.5 bottom-1.5 border-r border-b`} aria-hidden />
    </>
  );
}

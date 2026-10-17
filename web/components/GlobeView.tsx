"use client";

// Loaded only on the client via next/dynamic (three.js needs window).
import Globe, { type GlobeMethods } from "react-globe.gl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GlobePoint, SpreadResponse } from "@/lib/types";
import { ACCENT, scoreColor, signed } from "@/lib/sentiment";

export type GlobeMode = "sentiment" | "spread";

interface Props {
  mode: GlobeMode;
  points: GlobePoint[];
  spread: SpreadResponse | null;
  selectedId: string | null;
  autoRotate: boolean;
  focus: { lat: number; lng: number; altitude?: number; key: string } | null;
  onSelect: (p: GlobePoint) => void;
  onInteract: () => void;
}

type HtmlDatum =
  | { kind: "hot"; lat: number; lng: number; p: GlobePoint; selected: boolean; showLabel: boolean }
  | { kind: "node"; lat: number; lng: number; label: string; first: boolean };

type RingDatum = { lat: number; lng: number; color: string; maxR: number; speed: number; period: number };
type ArcDatum = { startLat: number; startLng: number; endLat: number; endLng: number; delay: number };

export default function GlobeView({ mode, points, spread, selectedId, autoRotate, focus, onSelect, onInteract }: Props) {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 600 });
  const [ready, setReady] = useState(false);
  const onSelectRef = useRef(onSelect);
  const onInteractRef = useRef(onInteract);
  onSelectRef.current = onSelect;
  onInteractRef.current = onInteract;

  // Responsive sizing
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect;
      setSize({ w: Math.max(200, Math.floor(width)), h: Math.max(200, Math.floor(height)) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Controls setup once the globe is ready
  useEffect(() => {
    if (!ready || !globeRef.current) return;
    const g = globeRef.current;
    const c = g.controls();
    c.autoRotateSpeed = 0.45;
    c.enableDamping = true;
    c.minDistance = 160;
    c.maxDistance = 600;
    const onStart = () => onInteractRef.current();
    c.addEventListener("start", onStart);
    g.pointOfView({ lat: 28, lng: -15, altitude: 2.3 }, 0);
    return () => c.removeEventListener("start", onStart);
  }, [ready]);

  useEffect(() => {
    if (!ready || !globeRef.current) return;
    globeRef.current.controls().autoRotate = autoRotate;
  }, [autoRotate, ready]);

  // Fly to focus target
  useEffect(() => {
    if (!ready || !globeRef.current || !focus) return;
    globeRef.current.pointOfView({ lat: focus.lat, lng: focus.lng, altitude: focus.altitude ?? 1.7 }, 1400);
  }, [focus, ready]);

  // ---- layers -------------------------------------------------------------
  const htmlData: HtmlDatum[] = useMemo(() => {
    if (mode === "sentiment") {
      return points.map((p) => ({
        kind: "hot" as const, lat: p.lat, lng: p.lon, p,
        selected: p.region_id === selectedId,
        showLabel: p.region_id === selectedId || p.norm_volume >= 0.55,
      }));
    }
    if (!spread) return [];
    return spread.steps.map((s, i) => ({
      kind: "node" as const, lat: s.lat, lng: s.lon,
      label: `${s.name} · ${s.hours === 0 ? "0h" : `+${s.hours}h`}`, first: i === 0,
    }));
  }, [mode, points, spread, selectedId]);

  const rings: RingDatum[] = useMemo(() => {
    if (mode === "sentiment") {
      return points.map((p) => ({
        lat: p.lat, lng: p.lon,
        color: p.region_id === selectedId ? "rgba(255,255,255,1)" : scoreColor(p.score),
        maxR: 2 + p.norm_volume * 4.5,
        speed: 1.2 + p.norm_volume * 1.5,
        period: 1600 - p.norm_volume * 600,
      }));
    }
    return (spread?.steps ?? []).map((s) => ({ lat: s.lat, lng: s.lon, color: ACCENT, maxR: 3.5, speed: 2, period: 1400 }));
  }, [mode, points, spread, selectedId]);

  const arcs: ArcDatum[] = useMemo(() => {
    if (mode !== "spread" || !spread) return [];
    const byId = new Map(spread.steps.map((s) => [s.region_id, s]));
    return spread.arcs
      .map(([a, b], i) => {
        const A = byId.get(a), B = byId.get(b);
        return A && B ? { startLat: A.lat, startLng: A.lon, endLat: B.lat, endLng: B.lon, delay: i } : null;
      })
      .filter((x): x is ArcDatum => !!x);
  }, [mode, spread]);

  const makeEl = useCallback((d: object): HTMLElement => {
    const datum = d as HtmlDatum;
    const el = document.createElement("div");
    if (datum.kind === "hot") {
      const { p, selected, showLabel } = datum;
      const r = Math.round(18 + p.norm_volume * 34);
      const c = scoreColor(p.score);
      el.className = "pulse-hot" + (selected ? " is-selected" : "");
      el.style.setProperty("--r", `${r}px`);
      el.style.setProperty("--c", c);
      el.style.setProperty("--c0", scoreColor(p.score, 0));
      el.innerHTML =
        `<span class="pulse-hot__glow"></span><span class="pulse-hot__core"></span>` +
        (selected ? `<span class="pulse-hot__sel"></span>` : "") +
        (showLabel ? `<span class="pulse-hot__label">${escapeHtml(p.name)} <b>${signed(p.score)}</b></span>` : "");
      el.title = `${p.name}: ${signed(p.score)} · ${p.volume.toLocaleString()} posts`;
      el.style.pointerEvents = "auto";
      el.onclick = (e) => { e.stopPropagation(); onSelectRef.current(p); };
    } else {
      el.className = "pulse-node" + (datum.first ? " is-first" : "");
      el.innerHTML = `<span class="pulse-node__dot"></span><span class="pulse-node__label">${escapeHtml(datum.label)}</span>`;
    }
    return el;
  }, []);

  return (
    <div ref={wrapRef} className="absolute inset-0">
      <Globe
        ref={globeRef}
        width={size.w}
        height={size.h}
        onGlobeReady={() => setReady(true)}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl="/globe/earth-night.jpg"
        bumpImageUrl="/globe/earth-topology.png"
        showAtmosphere
        atmosphereColor="#4C9BFF"
        atmosphereAltitude={0.2}
        showGraticules
        // hotspots / spread nodes
        htmlElementsData={htmlData}
        htmlLat="lat"
        htmlLng="lng"
        htmlAltitude={0.01}
        htmlElement={makeEl}
        htmlTransitionDuration={0}
        // pulse rings
        ringsData={rings}
        ringLat="lat"
        ringLng="lng"
        ringColor={(d: object) => {
          const base = (d as RingDatum).color;
          return (t: number) => withAlpha(base, Math.max(0, 0.85 * (1 - t)));
        }}
        ringMaxRadius="maxR"
        ringPropagationSpeed="speed"
        ringRepeatPeriod="period"
        ringAltitude={0.004}
        // spread arcs
        arcsData={arcs}
        arcColor={() => [withAlpha(ACCENT, 0.35), ACCENT]}
        arcDashLength={0.35}
        arcDashGap={0.15}
        arcDashInitialGap={(d: object) => (d as ArcDatum).delay * 0.5}
        arcDashAnimateTime={1800}
        arcStroke={0.7}
        arcAltitudeAutoScale={0.45}
        arcsTransitionDuration={600}
      />
    </div>
  );
}

function withAlpha(color: string, a: number): string {
  if (color.startsWith("rgba(")) return color.replace(/,\s*[\d.]+\)$/, `,${a.toFixed(3)})`);
  if (color.startsWith("#")) {
    const n = parseInt(color.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a.toFixed(3)})`;
  }
  return color;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

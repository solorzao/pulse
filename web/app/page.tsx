"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, onDataSource } from "@/lib/api";
import type { AskResponse, GlobePoint, RegionDetail, SpreadResponse, Topic, TrendingItem } from "@/lib/types";
import { compact, scoreTextColor, signed } from "@/lib/sentiment";
import type { GlobeMode } from "@/components/GlobeView";
import { RegionCard, SpreadCard } from "@/components/RegionCard";
import { AskBar, AskDrawer } from "@/components/Ask";

const GlobeView = dynamic(() => import("@/components/GlobeView"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="h-[min(70vw,520px)] w-[min(70vw,520px)] animate-pulse rounded-full bg-[radial-gradient(circle_at_38%_32%,#11233A,#070D16)] shadow-[0_0_80px_rgba(76,155,255,0.18)]" />
    </div>
  ),
});

type Focus = { lat: number; lng: number; altitude?: number; key: string };

function pickDefault(points: GlobePoint[]): GlobePoint | undefined {
  return [...points].sort(
    (a, b) => Math.abs(b.score) * Math.sqrt(b.norm_volume) - Math.abs(a.score) * Math.sqrt(a.norm_volume),
  )[0];
}

export default function Home() {
  const [mode, setMode] = useState<GlobeMode>("sentiment");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicId, setTopicId] = useState("ai-datacenters");
  const [points, setPoints] = useState<GlobePoint[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [region, setRegion] = useState<RegionDetail | null>(null);
  const [regionLoading, setRegionLoading] = useState(false);
  const [spread, setSpread] = useState<SpreadResponse | null>(null);
  const [trending, setTrending] = useState<TrendingItem[]>([]);
  const [autoRotate, setAutoRotate] = useState(true);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [usingMock, setUsingMock] = useState(false);

  const [question, setQuestion] = useState("");
  const [askOpen, setAskOpen] = useState(false);
  const [askBusy, setAskBusy] = useState(false);
  const [askQ, setAskQ] = useState("");
  const [askRes, setAskRes] = useState<AskResponse | null>(null);
  const [askErr, setAskErr] = useState<string | null>(null);

  const regionReq = useRef(0);
  const flyOnLoad = useRef(false);

  useEffect(() => onDataSource(setUsingMock), []);

  // Initial loads
  useEffect(() => {
    api.topics().then(setTopics);
    api.trending().then(setTrending);
    api.spread().then(setSpread);
  }, []);

  const loadRegion = useCallback((topic: string, regionId: string) => {
    const id = ++regionReq.current;
    setRegionLoading(true);
    api.region(topic, regionId).then((r) => {
      if (id !== regionReq.current) return;
      setRegion(r);
      setRegionLoading(false);
    });
  }, []);

  // Globe points per topic; preselect the most striking region
  useEffect(() => {
    let alive = true;
    setPoints([]);
    api.globe(topicId).then((g) => {
      if (!alive) return;
      setPoints(g.points);
      const d = pickDefault(g.points);
      if (d) {
        setSelectedId(d.region_id);
        loadRegion(topicId, d.region_id);
        if (flyOnLoad.current) {
          flyOnLoad.current = false;
          setFocus({ lat: Math.max(-50, Math.min(55, d.lat * 0.85)), lng: d.lon, altitude: 1.8, key: "t" + topicId });
        }
      }
    });
    return () => { alive = false; };
  }, [topicId, loadRegion]);

  const topic = topics.find((t) => t.id === topicId);
  const topicName = topic?.name ?? topicId;

  const selectPoint = useCallback(
    (p: GlobePoint) => {
      setSelectedId(p.region_id);
      setAutoRotate(false);
      setFocus({ lat: Math.max(-50, Math.min(55, p.lat * 0.85)), lng: p.lon, altitude: 1.6, key: p.region_id + Date.now() });
      loadRegion(topicId, p.region_id);
    },
    [topicId, loadRegion],
  );

  const pickTopic = (id: string) => {
    if (id === topicId) return;
    setTopicId(id);
    setRegion(null);
    setAutoRotate(false);
    flyOnLoad.current = true;
  };

  const pickMode = (m: GlobeMode) => {
    setMode(m);
    setAutoRotate(false);
    if (m === "spread") setFocus({ lat: 12, lng: 150, altitude: 2.7, key: "spread" + Date.now() });
    else {
      const p = points.find((x) => x.region_id === selectedId);
      if (p) setFocus({ lat: p.lat * 0.85, lng: p.lon, altitude: 1.8, key: "sent" + Date.now() });
    }
  };

  const ask = useCallback(
    async (q: string) => {
      setAskQ(q);
      setAskOpen(true);
      setAskBusy(true);
      setAskRes(null);
      setAskErr(null);
      try {
        const res = await api.ask({ question: q, topic: topicId, region_id: mode === "sentiment" ? selectedId : null });
        setAskRes(res);
      } catch (e) {
        setAskErr(String(e));
      } finally {
        setAskBusy(false);
      }
    },
    [topicId, selectedId, mode],
  );

  const selectedName = points.find((p) => p.region_id === selectedId)?.name;
  const askContext = mode === "spread" ? "Spread · dance challenge" : `${topicName}${selectedName ? ` · ${selectedName}` : ""}`;

  return (
    <div className="flex min-h-screen flex-col bg-ground text-ink lg:h-screen lg:overflow-hidden">
      <Header usingMock={usingMock} />

      <div className="flex min-h-0 flex-1 flex-col gap-5 px-4 py-4 sm:px-6 lg:flex-row lg:gap-5 lg:py-5">
        {/* Left: controls */}
        <aside aria-label="Controls" className="order-2 flex min-h-0 flex-col gap-[18px] lg:order-1 lg:w-[268px] lg:shrink-0 lg:overflow-y-auto lg:pr-1">
          <div className="flex flex-col gap-2">
            <span className="text-xs text-muted">View</span>
            <div className="flex gap-1 rounded-[10px] border border-line bg-panel p-1">
              {(["sentiment", "spread"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => pickMode(m)}
                  className={`h-[38px] flex-1 rounded-[7px] font-medium transition ${mode === m ? "bg-[#2A333E] text-white" : "text-muted hover:text-ink"}`}
                >
                  {m === "sentiment" ? "Sentiment" : "Spread"}
                </button>
              ))}
            </div>
          </div>

          {mode === "sentiment" ? (
            <>
              <div className="flex flex-col gap-2">
                <span className="text-xs text-muted">Topic</span>
                {topics.length === 0 &&
                  [0, 1, 2].map((i) => <div key={i} className="h-[52px] animate-pulse rounded-[10px] border border-line bg-panel" />)}
                {topics.map((t) => {
                  const on = t.id === topicId;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => pickTopic(t.id)}
                      className={`min-h-11 rounded-[10px] border px-3.5 py-2 text-left transition ${
                        on ? "border-[#4A5868] bg-[#1B2430] text-white" : "border-line text-ink2 hover:border-line2"
                      }`}
                    >
                      {t.name}
                      <span className="block text-xs text-muted">
                        {compact(t.post_count)} posts · mood{" "}
                        <span className="font-mono" style={{ color: scoreTextColor(t.mood) }}>{signed(t.mood)}</span>
                      </span>
                    </button>
                  );
                })}
                <label className="flex h-11 items-center gap-2 rounded-[10px] border border-dashed border-line2 px-3">
                  <span className="sr-only">Track a new topic</span>
                  <input
                    type="text"
                    placeholder="+ Track any topic, place or brand"
                    className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-ink outline-none placeholder:text-muted"
                    onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).value = ""; }}
                  />
                </label>
              </div>
              <div className="flex flex-col gap-2 text-xs text-muted">
                <div className="flex items-center gap-2">
                  <span>Negative</span>
                  <span className="h-2 flex-1 rounded bg-[linear-gradient(90deg,#FF8A3D,#A7B0BD_50%,#4C9BFF)]" />
                  <span>Positive</span>
                </div>
                <span>Glow size = how much people are posting</span>
              </div>
            </>
          ) : (
            <div className="flex flex-col gap-2 rounded-xl border border-line bg-panel p-3.5">
              <span className="text-xs text-muted">Tracing</span>
              <span className="font-semibold">{spread?.name ?? "New dance challenge"}</span>
              <span className="text-xs text-muted">
                Arcs show where the trend jumped next, matched by audio fingerprint and video frames.
              </span>
            </div>
          )}

          <Trending items={trending} />

          <button
            type="button"
            onClick={() => setAutoRotate((a) => !a)}
            className="mt-auto h-11 shrink-0 rounded-[10px] border border-line2 text-ink transition hover:bg-panel"
          >
            {autoRotate ? "Pause rotation" : "Resume rotation"}
          </button>
        </aside>

        {/* Center: globe */}
        <section aria-label="Globe" className="relative order-1 h-[62vh] min-h-[360px] min-w-0 lg:order-2 lg:h-auto lg:flex-1">
          <GlobeView
            mode={mode}
            points={points}
            spread={spread}
            selectedId={selectedId}
            autoRotate={autoRotate}
            focus={focus}
            onSelect={selectPoint}
            onInteract={() => setAutoRotate(false)}
          />
          {mode === "sentiment" && (
            <div className="pointer-events-none absolute left-2 top-1 font-mono text-[11px] text-muted">
              {topicName} · {points.length} regions · last 30 days
            </div>
          )}
        </section>

        {/* Right: region card */}
        <aside
          aria-label="Details"
          className="order-3 flex min-h-0 flex-col gap-3.5 rounded-[14px] border border-line bg-panel p-[18px] lg:w-[360px] lg:shrink-0 lg:overflow-y-auto"
        >
          {mode === "sentiment" ? (
            <RegionCard region={region} topicName={topicName} loading={regionLoading} />
          ) : (
            <SpreadCard spread={spread} />
          )}
        </aside>
      </div>

      <div className="px-4 pb-5 sm:px-6">
        <AskBar value={question} onChange={setQuestion} onSubmit={ask} busy={askBusy} context={askContext} />
      </div>

      <AskDrawer
        open={askOpen}
        loading={askBusy}
        question={askQ}
        response={askRes}
        error={askErr}
        onClose={() => setAskOpen(false)}
      />
    </div>
  );
}

function Header({ usingMock }: { usingMock: boolean }) {
  const [rate, setRate] = useState(4820);
  useEffect(() => {
    const t = setInterval(() => setRate((r) => Math.max(4100, Math.min(5600, r + Math.round((Math.random() - 0.48) * 90)))), 1500);
    return () => clearInterval(t);
  }, []);
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-[#161C24] px-4 py-3.5 sm:px-6">
      <div className="flex items-center gap-2.5">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
          <circle cx="14" cy="14" r="12" stroke="#E8ECF1" strokeWidth="1.6" />
          <path d="M4 15h5l2.5-6 4 11 2.5-5H24" stroke="#C8F25A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-[19px] font-bold">Pulse</span>
      </div>
      <span className="hidden text-[13px] text-muted sm:inline">Drag the globe to spin it. Click a glow to open a region.</span>
      <div className="ml-auto flex items-center gap-2 font-mono text-xs text-muted">
        <span className="live-dot h-2 w-2 rounded-full bg-accent" />
        <span>LIVE · {rate.toLocaleString()} posts/min</span>
        <span
          className="ml-1 rounded border border-line px-1.5 py-px text-[10px] tracking-wide text-muted/80"
          title={usingMock ? "API unreachable — showing bundled demo data" : "Seeded demo dataset"}
        >
          DEMO DATA{usingMock ? " · OFFLINE" : ""}
        </span>
      </div>
    </header>
  );
}

function Trending({ items }: { items: TrendingItem[] }) {
  const [open, setOpen] = useState(true);
  const list = useMemo(() => [...items].sort((a, b) => b.velocity - a.velocity || b.count - a.count).slice(0, 5), [items]);
  if (!items.length) return null;
  return (
    <section className="flex flex-col gap-1 rounded-xl border border-line bg-panel p-3.5">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex items-center gap-2 text-left">
        <span className="text-[13px] font-semibold">Trending worldwide</span>
        <span className="live-dot h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="ml-auto text-xs text-muted">{open ? "−" : "+"}</span>
      </button>
      {open &&
        list.map((t, i) => (
          <div key={t.id} className={`flex flex-col gap-0.5 py-2 ${i < list.length - 1 ? "border-b border-track" : ""}`}>
            <div className="flex items-baseline gap-2">
              <span className="text-[13px] font-medium leading-snug">{t.name}</span>
              <span
                className="ml-auto shrink-0 font-mono text-[11px]"
                style={{ color: t.velocity > 0 ? "#C8F25A" : t.velocity < 0 ? "#FFB27E" : "#9AA4B2" }}
              >
                {t.velocity > 0 ? "▲".repeat(Math.min(3, t.velocity)) : t.velocity < 0 ? "▼".repeat(Math.min(3, -t.velocity)) : "•"}
              </span>
            </div>
            <span className="text-[11px] text-muted">
              {t.category} · {t.format} · {compact(t.count)} posts ·{" "}
              <span style={{ color: scoreTextColor(Math.round(t.sentiment * 100)) }}>{signed(Math.round(t.sentiment * 100))}</span>
            </span>
          </div>
        ))}
    </section>
  );
}

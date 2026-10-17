"use client";

import { useEffect, useMemo, useState } from "react";
import type { AskResponse, Citation } from "@/lib/types";

export const SUGGESTIONS = [
  "Why is Ireland so negative?",
  "Compare Jakarta and Singapore",
  "What's going viral right now?",
];

const LOADING_TOOLS = [
  "get_topics",
  "get_globe",
  "get_region",
  "search_posts",
  "get_trend",
  "read_media_captions",
  "get_trending",
  "compose_answer",
];

export function AskBar({
  value, onChange, onSubmit, busy, context,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: (q: string) => void;
  busy: boolean;
  context: string;
}) {
  return (
    <div className="mx-auto flex w-full max-w-[920px] flex-col gap-2.5">
      <form
        onSubmit={(e) => { e.preventDefault(); if (value.trim() && !busy) onSubmit(value.trim()); }}
        className="flex flex-wrap items-center gap-2.5 rounded-[14px] border border-line2 bg-panel p-2 shadow-[0_8px_40px_rgba(0,0,0,0.5)]"
      >
        <label className="flex h-12 min-w-0 flex-[1_1_300px] items-center gap-2 px-3">
          <span className="sr-only">Ask about what you see</span>
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Ask about what you see… e.g. why is Ireland so negative?"
            className="min-w-0 flex-1 border-0 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted"
          />
          <span className="hidden shrink-0 rounded-md border border-line px-2 py-0.5 font-mono text-[11px] text-muted md:inline">
            {context}
          </span>
        </label>
        <button
          type="submit"
          disabled={busy}
          className="h-12 rounded-[10px] bg-accent px-5 font-semibold text-ground transition hover:brightness-110 disabled:opacity-50"
        >
          {busy ? "Thinking…" : "Ask Pulse"}
        </button>
      </form>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => { onChange(s); onSubmit(s); }}
            className="h-8 rounded-full border border-line bg-panel/70 px-3.5 text-[13px] text-ink2 transition hover:border-line2 hover:text-ink disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

const TONE: Record<string, { bg: string; fg: string; dot: string }> = {
  positive: { bg: "rgba(76,155,255,0.14)", fg: "#7DB6FF", dot: "#4C9BFF" },
  negative: { bg: "rgba(255,138,61,0.14)", fg: "#FFB27E", dot: "#FF8A3D" },
  mixed: { bg: "rgba(167,176,189,0.14)", fg: "#C9CFD8", dot: "#A7B0BD" },
};

export function AskDrawer({
  open, loading, question, response, error, onClose,
}: {
  open: boolean;
  loading: boolean;
  question: string;
  response: AskResponse | null;
  error: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button aria-label="Close answer" className="absolute inset-0 bg-ground/60 backdrop-blur-[2px]" onClick={onClose} />
      <aside
        className="drawer-in relative flex h-full w-full max-w-[720px] flex-col overflow-y-auto border-l border-line bg-[#080B10] shadow-2xl"
        aria-label="Answer"
      >
        <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-[#080B10]/95 px-6 py-3.5 backdrop-blur">
          <span className="font-mono text-xs text-muted">Ask Pulse</span>
          <span className="truncate text-sm text-ink2">&ldquo;{question}&rdquo;</span>
          <button onClick={onClose} className="ml-auto rounded-md border border-line px-2.5 py-1 text-xs text-muted hover:text-ink">
            Close · Esc
          </button>
        </div>
        <div className="p-6">
          {loading && <ToolTicker />}
          {!loading && error && <div className="rounded-xl border border-neg/40 bg-neg/10 p-4 text-sm">{error}</div>}
          {!loading && response && <Report r={response} />}
        </div>
      </aside>
    </div>
  );
}

function ToolTicker() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => x + 1), 650);
    return () => clearInterval(t);
  }, []);
  const shown = Math.min(i + 1, LOADING_TOOLS.length);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-sm text-ink2">
        <span className="live-dot h-2 w-2 rounded-full bg-accent" />
        Pulse is reading posts, photos and video…
      </div>
      <ol className="flex flex-col gap-1.5 font-mono text-[13px]">
        {LOADING_TOOLS.slice(0, shown).map((t, idx) => {
          const done = idx < shown - 1 || shown === LOADING_TOOLS.length;
          return (
            <li key={t} className="fade-in flex items-center gap-2.5 rounded-lg bg-panel px-3 py-2">
              <span className={done ? "text-accent" : "text-muted"}>{done ? "✓" : "›"}</span>
              <span className={done ? "text-ink2" : "text-ink"}>{t}()</span>
              {!done && <span className="ml-auto h-1 w-16 overflow-hidden rounded bg-track"><span className="block h-1 w-1/2 animate-pulse bg-accent" /></span>}
            </li>
          );
        })}
      </ol>
      <div className="flex flex-col gap-2 pt-2">
        <div className="h-8 w-3/4 animate-pulse rounded bg-panel" />
        <div className="h-4 w-full animate-pulse rounded bg-panel" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-panel" />
      </div>
    </div>
  );
}

function Report({ r }: { r: AskResponse }) {
  const a = r.answer;
  const tone = TONE[a.tone] ?? TONE.mixed;
  const [active, setActive] = useState<number | null>(null);
  const citeMap = useMemo(() => new Map(a.citations.map((c) => [c.n, c])), [a.citations]);
  const activeCite = active != null ? citeMap.get(active) : null;

  return (
    <article className="fade-in flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-muted">
        <span className="flex items-center gap-1.5 rounded-md px-2.5 py-1 font-sans text-[13px] font-semibold" style={{ background: tone.bg, color: tone.fg }}>
          <span className="h-2 w-2 rounded-full" style={{ background: tone.dot }} />
          {a.verdict}
        </span>
        <span className="rounded-md bg-panel px-2.5 py-1">{a.citations.length} cited posts</span>
        <span className="rounded-md bg-panel px-2.5 py-1">{r.tool_calls.length} tool calls</span>
        <span className="rounded-md bg-panel px-2.5 py-1">last 30 days</span>
        <span className={`rounded-md px-2.5 py-1 ${a.confidence.level === "high" ? "bg-pos/15 text-[#7DB6FF]" : a.confidence.level === "medium" ? "bg-neg/15 text-[#FFB27E]" : "bg-track"}`}>
          confidence: {a.confidence.level}
        </span>
      </div>

      <h2 className="m-0 max-w-[620px] text-[30px] font-semibold leading-[1.15] tracking-[-0.01em]">{a.summary}</h2>

      <div className="flex flex-col gap-3.5 text-[15px] leading-relaxed text-ink2">
        {a.paragraphs.map((p, i) => (
          <p key={i} className="m-0">
            {renderWithCitations(p, citeMap, active, setActive)}
          </p>
        ))}
      </div>

      {activeCite && <CitationCard c={activeCite} onClose={() => setActive(null)} />}

      {a.citations.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="m-0 text-xs font-semibold uppercase tracking-[0.06em] text-muted">What people are saying</h3>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
            {a.citations.map((c) => (
              <button
                key={c.n}
                onClick={() => setActive(c.n === active ? null : c.n)}
                className={`flex flex-col gap-2 rounded-[14px] border p-4 text-left transition ${
                  c.n === active ? "border-accent/60 bg-panel2" : "border-line bg-panel hover:border-line2"
                }`}
              >
                <span className="font-mono text-[11px] text-accent">[{c.n}]</span>
                <span className="text-sm text-ink">&ldquo;{c.text}&rdquo;</span>
                <span className="text-xs text-muted">{c.source}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="rounded-[10px] bg-note px-3.5 py-3 text-[13px] text-soft">
        <span className="mr-1 font-semibold text-ink2">How sure are we?</span> {a.confidence.note}
      </div>

      <section className="flex flex-col gap-2 border-t border-line pt-4">
        <h3 className="m-0 text-xs font-semibold uppercase tracking-[0.06em] text-muted">How this answer was made</h3>
        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[12px]">
          {r.tool_calls.map((t, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-line2">→</span>}
              <span className="rounded-md border border-line bg-panel px-2 py-1 text-ink2" title={JSON.stringify(t.args)}>
                {t.name}
                <span className="text-muted">({formatArgs(t.args)})</span>
              </span>
            </span>
          ))}
        </div>
      </section>
    </article>
  );
}

function formatArgs(args: Record<string, unknown>) {
  const vals = Object.values(args ?? {}).map((v) => (typeof v === "string" ? v : JSON.stringify(v)));
  const s = vals.join(", ");
  return s.length > 38 ? s.slice(0, 36) + "…" : s;
}

function renderWithCitations(
  text: string, map: Map<number, Citation>, active: number | null, setActive: (n: number | null) => void,
) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return <span key={i}>{part}</span>;
    const n = Number(m[1]);
    if (!map.has(n)) return <span key={i}>{part}</span>;
    const on = active === n;
    return (
      <button
        key={i}
        onClick={() => setActive(on ? null : n)}
        className={`mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded px-1 align-middle font-mono text-[11px] font-medium transition ${
          on ? "bg-accent text-ground" : "bg-accent/15 text-accent hover:bg-accent/30"
        }`}
        aria-label={`Show cited post ${n}`}
      >
        {n}
      </button>
    );
  });
}

function CitationCard({ c, onClose }: { c: Citation; onClose: () => void }) {
  return (
    <div className="fade-in flex flex-col gap-2 rounded-[14px] border border-accent/40 bg-panel2 p-4">
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="rounded bg-accent px-1.5 font-mono text-[11px] font-semibold text-ground">{c.n}</span>
        <span>{c.source}</span>
        <button onClick={onClose} className="ml-auto text-muted hover:text-ink" aria-label="Close citation">✕</button>
      </div>
      <p className="m-0 text-[15px]">&ldquo;{c.text}&rdquo;</p>
      {c.url && c.url !== "#" && (
        <a href={c.url} target="_blank" rel="noreferrer" className="text-xs">Open original post ↗</a>
      )}
    </div>
  );
}

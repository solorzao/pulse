"use client";

import type { EnrichedPost, RegionDetail, SpreadResponse } from "@/lib/types";
import { compact, scoreTextColor, sentimentBarColor, signed, scoreColor } from "@/lib/sentiment";

const SOURCE_LABEL: Record<string, string> = {
  bluesky: "Bluesky", reddit: "Reddit", youtube: "YouTube", tiktok: "TikTok", mastodon: "Mastodon", news: "News",
};

export function sourceLine(p: Pick<EnrichedPost, "source" | "community" | "author_loc">) {
  return [SOURCE_LABEL[p.source] ?? p.source, p.community, p.author_loc].filter(Boolean).join(" · ");
}

export function RegionCard({ region, topicName, loading }: { region: RegionDetail | null; topicName: string; loading: boolean }) {
  if (!region) {
    return (
      <div className="flex flex-col gap-3 text-muted">
        <div className="text-xs">Region pulse · {topicName}</div>
        <div className="h-6 w-40 animate-pulse rounded bg-track" />
        <div className="h-12 w-28 animate-pulse rounded bg-track" />
        <div className="h-24 animate-pulse rounded bg-track" />
      </div>
    );
  }
  const r = region;
  return (
    <div key={r.region_id + r.topic} className={`fade-in flex flex-col gap-4 ${loading ? "opacity-60" : ""} transition-opacity`}>
      <div>
        <div className="text-xs text-muted">Region pulse · {topicName}</div>
        <h2 className="mt-0.5 text-[22px] font-semibold">{r.name}</h2>
      </div>

      <div className="flex items-end gap-4">
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono text-[44px] font-medium leading-none" style={{ color: scoreTextColor(r.score) }}>
            {signed(r.score)}
          </span>
          <span className="text-sm">{r.mood_label}</span>
        </div>
        <Sparkline trend={r.trend} />
      </div>

      <div className="flex flex-col gap-2.5">
        <span className="text-xs text-muted">What&apos;s driving it</span>
        {r.narratives.map((n) => (
          <div key={n.label} className="flex flex-col gap-1">
            <div className="flex text-[13px]">
              <span>{n.label}</span>
              <span className="ml-auto font-mono text-muted">{Math.round(n.share * 100)}%</span>
            </div>
            <div className="h-1.5 rounded-sm bg-track">
              <div
                className="h-1.5 rounded-sm transition-[width] duration-700"
                style={{ width: `${Math.min(100, n.share * 200)}%`, background: sentimentBarColor(n.sentiment) }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2.5">
        <span className="text-xs text-muted">Evidence · top posts</span>
        {r.posts.map((p) => (
          <PostCard key={p.id} post={p} />
        ))}
      </div>

      <div className="rounded-[10px] bg-note px-3 py-2.5 text-xs text-soft">
        <span
          className={`mr-2 rounded px-1.5 py-0.5 font-mono text-[11px] uppercase ${
            r.confidence.level === "high" ? "bg-pos/15 text-[#7DB6FF]" : r.confidence.level === "medium" ? "bg-neg/15 text-[#FFB27E]" : "bg-track text-muted"
          }`}
        >
          {r.confidence.level} confidence
        </span>
        {r.confidence.note}
        <div className="mt-1 text-muted">{r.count.toLocaleString()} posts · photos &amp; video included</div>
      </div>
    </div>
  );
}

export function PostCard({ post: p, compactMode = false }: { post: EnrichedPost; compactMode?: boolean }) {
  const media = p.media?.[0];
  const hasVision = !!(p.caption || p.ocr || media);
  return (
    <article className="flex flex-col gap-2 rounded-[10px] bg-panel2 p-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: scoreColor(p.sentiment * 100) }} />
        <span className="truncate">{sourceLine(p)}</span>
        <span className="ml-auto shrink-0 font-mono">♥ {compact(p.engagement)}</span>
      </div>
      <p className="m-0 text-sm leading-snug">&ldquo;{p.text}&rdquo;</p>
      {hasVision && !compactMode && (
        <div className="flex overflow-hidden rounded-lg border border-line">
          <div className="striped-tile relative flex w-[88px] shrink-0 items-start p-1.5">
            <span className="rounded bg-ground/90 px-1.5 py-0.5 font-mono text-[10px] uppercase text-ink">
              {media?.type === "video" ? "Video" : "Photo"}
            </span>
          </div>
          <div className="flex min-w-0 flex-col gap-1 p-2 text-xs">
            {p.caption && (
              <div>
                <Tag>Vision</Tag> <span className="text-ink2">{p.caption}</span>
              </div>
            )}
            {p.ocr && (
              <div>
                <Tag>OCR</Tag> <span className="font-mono text-[11px] text-ink2">{p.ocr}</span>
              </div>
            )}
            {!p.caption && !p.ocr && media && <span className="text-ink2">{media.description}</span>}
          </div>
        </div>
      )}
    </article>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="mr-1 rounded bg-accent/15 px-1 py-px font-mono text-[10px] font-medium tracking-wide text-accent">
      {children}
    </span>
  );
}

function Sparkline({ trend }: { trend: { date: string; score: number }[] }) {
  if (!trend?.length) return null;
  const w = 120, h = 36;
  const min = Math.min(-10, ...trend.map((t) => t.score));
  const max = Math.max(10, ...trend.map((t) => t.score));
  const x = (i: number) => (i / Math.max(1, trend.length - 1)) * w;
  const y = (v: number) => h - ((v - min) / (max - min || 1)) * h;
  const pts = trend.map((t, i) => `${x(i).toFixed(1)},${y(t.score).toFixed(1)}`).join(" ");
  const last = trend[trend.length - 1].score;
  return (
    <div className="ml-auto flex flex-col items-end gap-0.5">
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-label="30-day mood trend">
        <line x1="0" x2={w} y1={y(0)} y2={y(0)} stroke="#2C3540" strokeDasharray="2 3" />
        <polyline points={pts} fill="none" stroke={scoreColor(last)} strokeWidth="1.8" strokeLinejoin="round" />
        <circle cx={x(trend.length - 1)} cy={y(last)} r="2.5" fill={scoreColor(last)} />
      </svg>
      <span className="font-mono text-[10px] text-muted">30 days</span>
    </div>
  );
}

export function SpreadCard({ spread }: { spread: SpreadResponse | null }) {
  if (!spread) return <div className="h-40 animate-pulse rounded bg-track" />;
  const total = spread.steps.reduce((a, s) => a + s.count, 0);
  const maxH = Math.max(...spread.steps.map((s) => s.hours));
  return (
    <div className="fade-in flex flex-col gap-3">
      <div>
        <div className="text-xs text-muted">Spread path · last {Math.max(6, maxH)}h</div>
        <h2 className="mt-0.5 text-[22px] font-semibold">{spread.name}</h2>
        <div className="mt-1 font-mono text-xs text-muted">
          {total.toLocaleString()} matching videos · {spread.steps.length} cities
        </div>
      </div>
      <div className="flex flex-col">
        {spread.steps.map((s) => (
          <div key={s.region_id} className="grid grid-cols-[52px_1fr] gap-2.5 border-b border-track py-2.5">
            <span className="font-mono text-xs text-accent">{s.hours === 0 ? "0h" : `+${s.hours}h`}</span>
            <div>
              <div className="flex items-baseline">
                <span className="font-semibold">{s.name}</span>
                <span className="ml-auto font-mono text-xs text-muted">{s.count.toLocaleString()}</span>
              </div>
              <div className="text-xs text-muted">{s.note}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-[10px] bg-note px-3 py-2.5 text-xs text-soft">
        <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />
        News hasn&apos;t covered this yet — mainstream outlets in none of these countries have picked it up.
      </div>
    </div>
  );
}

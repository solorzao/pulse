// Typed API client for the Pulse API (see CONTRACT.md).
// Every call falls back to bundled mock data if the API is unreachable or errors.
import type {
  AskRequest, AskResponse, GlobeResponse, RegionDetail, SpreadResponse, Topic, TrendingItem,
} from "./types";
import { mockAsk, mockGlobe, mockRegion, mockSpread, mockTopics, mockTrending } from "./mock";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

type Listener = (usingMock: boolean) => void;
const listeners = new Set<Listener>();
let usingMock = false;
export function onDataSource(fn: Listener) {
  listeners.add(fn);
  fn(usingMock);
  return () => { listeners.delete(fn); };
}
function setMock(v: boolean) {
  if (v !== usingMock) { usingMock = v; listeners.forEach((l) => l(v)); }
}

async function withFallback<T>(path: string, fallback: () => T, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  if (!API_URL) { setMock(true); return fallback(); }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = (await res.json()) as T;
    setMock(false);
    return data;
  } catch (err) {
    console.warn(`[pulse] ${path} failed, using mock data:`, err);
    setMock(true);
    return fallback();
  } finally {
    clearTimeout(timer);
  }
}

const q = encodeURIComponent;

export const api = {
  topics: () => withFallback<Topic[]>("/topics", mockTopics),
  globe: (topic: string, days = 30) =>
    withFallback<GlobeResponse>(`/globe?topic=${q(topic)}&days=${days}`, () => mockGlobe(topic)),
  region: (topic: string, regionId: string) =>
    withFallback<RegionDetail>(`/region?topic=${q(topic)}&region_id=${q(regionId)}`, () => mockRegion(topic, regionId)),
  spread: () => withFallback<SpreadResponse>("/spread", mockSpread),
  trending: () => withFallback<TrendingItem[]>("/trending", mockTrending),
  ask: async (body: AskRequest) => {
    const res = await withFallback<AskResponse>(
      "/ask", () => mockAsk(body), { method: "POST", body: JSON.stringify(body) }, 90000,
    );
    // When serving the mock, simulate agent latency so the loading state is visible.
    if (usingMock) await new Promise((r) => setTimeout(r, 2200));
    return res;
  },
};

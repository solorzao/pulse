// Types mirror CONTRACT.md exactly.

export type Source = "bluesky" | "reddit" | "youtube" | "tiktok" | "mastodon" | "news";

export interface Topic {
  id: string;
  name: string;
  post_count: number;
  mood: number; // -100..100
}

export interface GlobePoint {
  region_id: string;
  name: string;
  lat: number;
  lon: number;
  score: number; // -100..100
  volume: number;
  norm_volume: number; // 0..1
}

export interface GlobeResponse {
  topic: string;
  points: GlobePoint[];
}

export interface Media {
  type: "image" | "video";
  description: string;
  url: string | null;
}

export interface EnrichedPost {
  id: string;
  topic: string;
  source: Source;
  community: string | null;
  author_loc: string | null;
  lang: string;
  text: string;
  media: Media[];
  ts: string;
  url: string;
  engagement: number;
  sentiment: number;
  narrative: string;
  region_id: string;
  region_conf: number;
  caption: string | null;
  ocr: string | null;
}

export type ConfidenceLevel = "low" | "medium" | "high";

export interface Confidence {
  level: ConfidenceLevel;
  note: string;
}

export interface Narrative {
  label: string;
  share: number; // 0..1
  sentiment: number; // -1..1
}

export interface RegionDetail {
  region_id: string;
  name: string;
  topic: string;
  score: number;
  mood_label: string;
  count: number;
  narratives: Narrative[];
  posts: EnrichedPost[];
  trend: { date: string; score: number }[];
  confidence: Confidence;
}

export interface SpreadStep {
  region_id: string;
  hours: number;
  note: string;
  count: number;
  lat: number;
  lon: number;
  name: string;
}

export interface SpreadResponse {
  id: string;
  name: string;
  steps: SpreadStep[];
  arcs: [string, string][];
}

export interface TrendingItem {
  id: string;
  name: string;
  category: "Culture" | "News" | "Meme" | "Tech";
  regions: string[];
  format: string;
  velocity: number; // -3..3
  sentiment: number;
  count: number;
}

export interface Citation {
  n: number;
  post_id: string;
  source: string;
  text: string;
  url: string;
}

export interface AskAnswer {
  verdict: string;
  tone: "positive" | "negative" | "mixed";
  summary: string;
  paragraphs: string[];
  citations: Citation[];
  confidence: Confidence;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface AskResponse {
  answer: AskAnswer;
  tool_calls: ToolCall[];
}

export interface AskRequest {
  question: string;
  topic: string | null;
  region_id: string | null;
}

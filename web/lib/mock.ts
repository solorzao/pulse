// Bundled mock data matching CONTRACT.md + demo stories.
// Used automatically when the API is unreachable, so the demo never breaks.
import type {
  AskRequest,
  AskResponse,
  EnrichedPost,
  GlobeResponse,
  Narrative,
  RegionDetail,
  Source,
  SpreadResponse,
  Topic,
  TrendingItem,
} from "./types";
import { moodLabel } from "./sentiment";

type MockPost = {
  source: Source;
  community?: string;
  loc?: string;
  text: string;
  narrative: string;
  sentiment: number;
  media?: { type: "image" | "video"; description: string };
  caption?: string;
  ocr?: string;
  engagement: number;
};

type MockRegion = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  score: number;
  volume: number;
  narratives: [string, number, number][]; // label, share, sentiment
  posts: MockPost[];
  confidence?: { level: "low" | "medium" | "high"; note: string };
  trendShape?: "worsening-10d" | "dip-13d";
};

const TOPIC_NAMES: Record<string, string> = {
  "ai-datacenters": "AI datacenters",
  "electric-scooters": "Electric scooters",
  "four-day-week": "Four-day work week",
};

const REGIONS: Record<string, MockRegion[]> = {
  "ai-datacenters": [
    {
      id: "ireland", name: "Ireland", lat: 53.3, lon: -8.0, score: -38, volume: 3980, trendShape: "worsening-10d",
      narratives: [["Power grid strain", 0.41, -0.7], ["Water use", 0.26, -0.5], ["Jobs & investment", 0.18, 0.4], ["Tax & FDI", 0.15, 0.1]],
      confidence: { level: "high", note: "3,980 posts, 82% placed in Ireland with high confidence. Sentiment has fallen sharply over the last 10 days." },
      posts: [
        { source: "reddit", community: "r/ireland", loc: "Dublin", text: "We're told to cut energy at home while another server campus gets approved. Datacentres now use over a fifth of the grid.", narrative: "Power grid strain", sentiment: -0.82, engagement: 4210, media: { type: "image", description: "Screenshot of EirGrid amber alert" }, ocr: "EIRGRID: AMBER ALERT — system margin tight this evening. Please reduce non-essential use." },
        { source: "bluesky", loc: "Cork", text: "Another hyperscaler planning application in South Dublin. Who exactly is this grid for?", narrative: "Power grid strain", sentiment: -0.71, engagement: 1820 },
        { source: "tiktok", loc: "Dublin", text: "POV: you check your electricity bill after the datacentre down the road opens", narrative: "Power grid strain", sentiment: -0.64, engagement: 9800, media: { type: "video", description: "Person reacting to a bill" }, caption: "Woman holding an electricity bill, exaggerated shocked reaction, datacentre visible through window" },
        { source: "news", community: "Irish Times comments", loc: "Ireland", text: "Water usage figures for the Clonee campus are higher than what was in the original planning permission.", narrative: "Water use", sentiment: -0.58, engagement: 960 },
        { source: "reddit", community: "r/ireland", loc: "Meath", text: "Honestly the jobs are real though. My brother got hired as a technician and it's the best paying job in the county.", narrative: "Jobs & investment", sentiment: 0.42, engagement: 740 },
      ],
    },
    {
      id: "virginia-us", name: "Virginia", lat: 39.0, lon: -77.5, score: -29, volume: 5210,
      narratives: [["Noise & backup generators", 0.33, -0.7], ["Rising power bills", 0.29, -0.6], ["Local tax revenue", 0.21, 0.5], ["Land use", 0.17, -0.3]],
      posts: [
        { source: "reddit", community: "r/nova", loc: "Loudoun County, VA", text: "The hum never stops after 10pm. We moved here for the quiet.", narrative: "Noise & backup generators", sentiment: -0.74, engagement: 3120, media: { type: "video", description: "Night video of datacenter" }, caption: "Night-time footage of a lit datacenter wall with rooftop cooling units; audible low hum" },
        { source: "youtube", community: "Local news", loc: "Ashburn, VA", text: "Residents say power bills are up 18% since the new substation went in.", narrative: "Rising power bills", sentiment: -0.6, engagement: 2200 },
        { source: "reddit", community: "r/loudoun", loc: "Loudoun County, VA", text: "Datacenter tax revenue is why our schools are fully funded. People forget this.", narrative: "Local tax revenue", sentiment: 0.55, engagement: 1500 },
      ],
    },
    {
      id: "arizona-us", name: "Arizona", lat: 33.4, lon: -112.0, score: -24, volume: 2140,
      narratives: [["Water in a drought", 0.44, -0.7], ["Jobs", 0.22, 0.5], ["Land use", 0.15, -0.3], ["Heat & grid", 0.19, -0.4]],
      posts: [
        { source: "bluesky", loc: "Phoenix, AZ", text: "Millions of gallons of water, in a desert. Make it make sense.", narrative: "Water in a drought", sentiment: -0.78, engagement: 2600, media: { type: "image", description: "Dry canal" }, caption: "Cracked, nearly empty irrigation canal with a datacenter construction site behind it" },
        { source: "reddit", community: "r/phoenix", loc: "Mesa, AZ", text: "They say it's closed-loop cooling now. I'll believe it when the numbers are public.", narrative: "Water in a drought", sentiment: -0.35, engagement: 820 },
      ],
    },
    {
      id: "texas-us", name: "Texas", lat: 30.3, lon: -97.7, score: 3, volume: 3320,
      narratives: [["Jobs & tax base", 0.36, 0.5], ["Grid reliability", 0.31, -0.5], ["Land prices", 0.14, 0.0], ["Water", 0.19, -0.2]],
      posts: [
        { source: "youtube", community: "Austin local news", loc: "Austin, TX", text: "Good for the county budget, bad for the grid in August.", narrative: "Grid reliability", sentiment: -0.1, engagement: 1900 },
        { source: "reddit", community: "r/texas", loc: "Abilene, TX", text: "Our town went from dying to hiring. I'm not complaining.", narrative: "Jobs & tax base", sentiment: 0.6, engagement: 1300 },
      ],
    },
    {
      id: "netherlands", name: "Netherlands", lat: 52.3, lon: 5.0, score: -21, volume: 1460,
      narratives: [["Farmland lost", 0.35, -0.6], ["Water", 0.22, -0.4], ["Green power", 0.18, 0.4], ["Jobs", 0.25, 0.2]],
      posts: [
        { source: "mastodon", loc: "Zeewolde (translated from Dutch)", text: "Farmland turned into server halls. Our grandparents reclaimed this land from the sea for food.", narrative: "Farmland lost", sentiment: -0.66, engagement: 880, media: { type: "image", description: "Protest sign" }, ocr: "GEEN DATACENTER OP ONZE LANDBOUWGROND (No datacenter on our farmland)" },
      ],
    },
    {
      id: "sweden", name: "Sweden", lat: 59.3, lon: 18.0, score: 19, volume: 980,
      narratives: [["Clean hydro power", 0.38, 0.6], ["Jobs in the north", 0.27, 0.5], ["Electricity prices", 0.2, -0.4], ["Heat reuse", 0.15, 0.5]],
      posts: [
        { source: "reddit", community: "r/sweden", loc: "Luleå (translated from Swedish)", text: "If they have to be somewhere, better here on hydro. And the waste heat warms half the town.", narrative: "Clean hydro power", sentiment: 0.62, engagement: 990 },
      ],
    },
    {
      id: "hyderabad", name: "Hyderabad", lat: 17.4, lon: 78.5, score: 26, volume: 2870,
      narratives: [["Investment & jobs", 0.42, 0.7], ["Digital sovereignty", 0.23, 0.5], ["Water", 0.15, -0.4], ["Real estate", 0.2, 0.3]],
      posts: [
        { source: "youtube", community: "Telugu news", loc: "Hyderabad (translated from Telugu)", text: "Hyderabad is becoming the cloud capital. Three new campuses announced this quarter.", narrative: "Investment & jobs", sentiment: 0.74, engagement: 5400, media: { type: "video", description: "News segment" }, caption: "TV news anchor in front of graphic of a datacenter campus, ticker reads investment figures" },
      ],
    },
    {
      id: "johor", name: "Johor", lat: 1.5, lon: 103.7, score: 15, volume: 1210,
      narratives: [["Investment", 0.39, 0.6], ["Water & power", 0.28, -0.5], ["Spillover from Singapore", 0.17, 0.1], ["Jobs", 0.16, 0.4]],
      posts: [
        { source: "news", community: "Local news comments", loc: "Johor Bahru (translated from Malay)", text: "New jobs, but will the taps run dry?", narrative: "Water & power", sentiment: 0.05, engagement: 610 },
      ],
    },
    {
      id: "santiago", name: "Santiago", lat: -33.4, lon: -70.6, score: -18, volume: 760,
      narratives: [["Water in Santiago", 0.47, -0.6], ["Jobs", 0.18, 0.4], ["Transparency", 0.14, -0.5], ["Energy", 0.21, -0.1]],
      posts: [
        { source: "bluesky", loc: "Santiago (translated from Spanish)", text: "They promised it would use less water than it does. Cerrillos residents deserve the real numbers.", narrative: "Water in Santiago", sentiment: -0.58, engagement: 720 },
      ],
    },
  ],
  "electric-scooters": [
    {
      id: "jakarta", name: "Jakarta", lat: -6.2, lon: 106.8, score: 44, volume: 4100,
      narratives: [["Saves money on fuel", 0.38, 0.8], ["First-ride pride", 0.24, 0.8], ["Charging access", 0.16, -0.4], ["Gov subsidy", 0.22, 0.5]],
      posts: [
        { source: "tiktok", loc: "Jakarta (translated from Indonesian)", text: "Charging at home costs less than one week of petrol. Never going back.", narrative: "Saves money on fuel", sentiment: 0.86, engagement: 22000, media: { type: "video", description: "First ride" }, caption: "Rider shows off a new e-scooter in the rain, friends cheering from a warung" },
        { source: "youtube", loc: "Jakarta", text: "Unboxing the subsidised model — 6 million rupiah after the discount!", narrative: "Gov subsidy", sentiment: 0.7, engagement: 8400 },
        { source: "reddit", community: "r/indonesia", loc: "Bekasi", text: "Love mine but finding a charger outside the city is a nightmare.", narrative: "Charging access", sentiment: -0.3, engagement: 1100 },
      ],
    },
    {
      id: "ho-chi-minh-city", name: "Ho Chi Minh City", lat: 10.8, lon: 106.7, score: 38, volume: 3200,
      narratives: [["Delivery riders switching", 0.31, 0.7], ["Cleaner air", 0.22, 0.7], ["Battery swap queues", 0.15, -0.4], ["Cost", 0.32, 0.5]],
      posts: [
        { source: "youtube", loc: "Ho Chi Minh City (translated from Vietnamese)", text: "Half the riders at my stand went electric this year.", narrative: "Delivery riders switching", sentiment: 0.72, engagement: 6300, media: { type: "video", description: "Swap station" }, caption: "Row of delivery riders charging at a roadside battery swap station at dusk" },
      ],
    },
    {
      id: "bangkok", name: "Bangkok", lat: 13.75, lon: 100.5, score: 21, volume: 1900,
      narratives: [["Fuel savings", 0.33, 0.6], ["Flooding and batteries", 0.21, -0.5], ["Style", 0.18, 0.6], ["Traffic", 0.28, 0.1]],
      posts: [{ source: "reddit", community: "r/Thailand", loc: "Bangkok (translated from Thai)", text: "Silent and cheap, I'm sold.", narrative: "Fuel savings", sentiment: 0.6, engagement: 900 }],
    },
    {
      id: "manila", name: "Manila", lat: 14.6, lon: 121.0, score: 12, volume: 1300,
      narratives: [["Petrol prices", 0.4, 0.5], ["Road safety", 0.3, -0.3], ["Memes", 0.3, 0.3]],
      posts: [{ source: "reddit", community: "r/Philippines", loc: "Manila", text: "Me vs the petrol price, round 47.", narrative: "Petrol prices", sentiment: 0.3, engagement: 2400, media: { type: "image", description: "Meme" }, ocr: "ME: *buys e-scooter*  /  GAS STATION: *raises price again*  /  ME: 😎" }],
    },
    {
      id: "singapore", name: "Singapore", lat: 1.35, lon: 103.8, score: -17, volume: 1650, trendShape: "dip-13d",
      narratives: [["Fire risk in flats", 0.39, -0.8], ["Footpath safety", 0.3, -0.6], ["Commute convenience", 0.14, 0.5], ["Regulation", 0.17, -0.1]],
      confidence: { level: "medium", note: "1,650 posts. Sentiment dipped after a viral battery-fire video ~13 days ago and has not recovered." },
      posts: [
        { source: "reddit", community: "r/singapore", loc: "Singapore", text: "Nobody wants these charging in the corridor of a 30-storey block.", narrative: "Fire risk in flats", sentiment: -0.76, engagement: 5200 },
        { source: "bluesky", loc: "Tampines, Singapore", text: "This is the third one this year. Ban charging indoors already.", narrative: "Fire risk in flats", sentiment: -0.81, engagement: 3900, media: { type: "image", description: "Fire aftermath" }, caption: "Scorched HDB corridor after a battery fire, blackened ceiling, news watermark in corner" },
        { source: "news", community: "Straits Times comments", loc: "Singapore", text: "Footpaths are for walking. My mother was nearly hit twice this week.", narrative: "Footpath safety", sentiment: -0.6, engagement: 1400 },
      ],
    },
    {
      id: "paris", name: "Paris", lat: 48.85, lon: 2.35, score: -22, volume: 1480,
      narratives: [["Rental clutter", 0.36, -0.7], ["Pedestrian safety", 0.28, -0.6], ["Last-mile commute", 0.17, 0.5], ["Ban debate", 0.19, -0.2]],
      posts: [{ source: "bluesky", loc: "Paris (translated from French)", text: "Good riddance to the rentals on every corner.", narrative: "Rental clutter", sentiment: -0.55, engagement: 1700, media: { type: "image", description: "Scooters piled" }, caption: "Pile of rental e-scooters tipped over on a narrow Paris pavement" }],
    },
    {
      id: "los-angeles", name: "Los Angeles", lat: 34.0, lon: -118.2, score: 9, volume: 1120,
      narratives: [["Short trips", 0.3, 0.6], ["Bike lane gaps", 0.26, -0.5], ["Theft", 0.15, -0.6], ["Beach path", 0.29, 0.6]],
      posts: [{ source: "reddit", community: "r/LosAngeles", loc: "Venice, CA", text: "Great for the beach path, terrifying on Lincoln.", narrative: "Bike lane gaps", sentiment: 0.1, engagement: 1300 }],
    },
  ],
  "four-day-week": [
    {
      id: "united-kingdom", name: "United Kingdom", lat: 52.5, lon: -1.5, score: 34, volume: 4560,
      narratives: [["Better wellbeing", 0.37, 0.8], ["Trial results", 0.26, 0.7], ["Small business worries", 0.17, -0.5], ["Productivity", 0.2, 0.4]],
      posts: [{ source: "reddit", community: "r/unitedkingdom", loc: "Manchester", text: "Our trial ended and nobody wants to go back.", narrative: "Trial results", sentiment: 0.8, engagement: 6100, media: { type: "image", description: "Chart" }, ocr: "4-DAY WEEK PILOT: 56 of 61 companies continuing · burnout down 71%" }],
    },
    {
      id: "germany", name: "Germany", lat: 51.0, lon: 10.0, score: 22, volume: 2980,
      narratives: [["Labour shortage fix", 0.3, 0.6], ["Productivity doubts", 0.25, -0.5], ["Family time", 0.21, 0.7], ["Unions", 0.24, 0.4]],
      posts: [{ source: "mastodon", loc: "Berlin (translated from German)", text: "Fewer days might be how we attract workers at all.", narrative: "Labour shortage fix", sentiment: 0.5, engagement: 800 }],
    },
    {
      id: "new-york-us", name: "New York", lat: 40.7, lon: -74.0, score: 18, volume: 3870,
      narratives: [["Burnout", 0.34, 0.6], ["Doesn't fit my industry", 0.24, -0.4], ["Recruiting perk", 0.19, 0.5], ["Pay trade-offs", 0.23, 0.1]],
      posts: [{ source: "tiktok", loc: "New York, NY", text: "I'd take a pay freeze for Fridays off.", narrative: "Burnout", sentiment: 0.6, engagement: 14000, media: { type: "video", description: "Office vlog" }, caption: "Office worker walking out of a Manhattan building on Thursday evening, caption 'my weekend starts now'" }],
    },
    {
      id: "tokyo", name: "Tokyo", lat: 35.7, lon: 139.7, score: 8, volume: 1740,
      narratives: [["Overwork culture", 0.33, 0.5], ["Unpaid overtime anyway", 0.27, -0.6], ["Government push", 0.16, 0.4], ["Childcare", 0.24, 0.3]],
      posts: [{ source: "bluesky", loc: "Tokyo (translated from Japanese)", text: "Four days on paper, five in practice.", narrative: "Unpaid overtime anyway", sentiment: -0.3, engagement: 1500 }],
    },
    {
      id: "sydney", name: "Sydney", lat: -33.9, lon: 151.2, score: 29, volume: 1520,
      narratives: [["Work-life balance", 0.39, 0.7], ["Rostering pain", 0.18, -0.4], ["Commute savings", 0.17, 0.6], ["Trials", 0.26, 0.5]],
      posts: [{ source: "reddit", community: "r/sydney", loc: "Sydney", text: "Long weekends every week, why not.", narrative: "Work-life balance", sentiment: 0.7, engagement: 1100 }],
    },
    {
      id: "bangalore", name: "Bangalore", lat: 13.0, lon: 77.6, score: -6, volume: 1310,
      narratives: [["Longer days instead", 0.33, -0.6], ["Startup hustle", 0.24, -0.4], ["Commute relief", 0.22, 0.6], ["Global clients", 0.21, -0.1]],
      posts: [{ source: "youtube", loc: "Bengaluru", text: "Four 12-hour days is not a gift.", narrative: "Longer days instead", sentiment: -0.6, engagement: 2900 }],
    },
    {
      id: "seoul", name: "Seoul", lat: 37.5, lon: 127.0, score: 11, volume: 1890,
      narratives: [["Shorter hours law", 0.32, 0.5], ["Competitiveness", 0.28, -0.4], ["Birth rate", 0.2, 0.4], ["Wellbeing", 0.2, 0.6]],
      posts: [{ source: "news", community: "Naver comments", loc: "Seoul (translated from Korean)", text: "If it helps people actually have families, try it.", narrative: "Birth rate", sentiment: 0.45, engagement: 1600 }],
    },
  ],
};

// ---- builders ---------------------------------------------------------------

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

function dateNDaysAgo(n: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

function buildTrend(r: MockRegion): { date: string; score: number }[] {
  const out: { date: string; score: number }[] = [];
  for (let i = 29; i >= 0; i--) {
    let s = r.score + (hash(r.id + i) - 0.5) * 8;
    if (r.trendShape === "worsening-10d") s = i > 10 ? -18 + (hash(r.id + i) - 0.5) * 6 : -18 + ((10 - i) / 10) * (r.score + 18);
    if (r.trendShape === "dip-13d") s = i > 13 ? 3 + (hash(r.id + i) - 0.5) * 5 : r.score + (hash(r.id + i) - 0.5) * 4;
    out.push({ date: dateNDaysAgo(i), score: Math.round(s) });
  }
  out[out.length - 1].score = r.score;
  return out;
}

function toPost(topic: string, r: MockRegion, p: MockPost, i: number): EnrichedPost {
  return {
    id: `${topic}-${r.id}-${i}`,
    topic,
    source: p.source,
    community: p.community ?? null,
    author_loc: p.loc ?? r.name,
    lang: "en",
    text: p.text,
    media: p.media ? [{ ...p.media, url: null }] : [],
    ts: new Date(Date.now() - (i + 1) * 3600_000 * 7).toISOString(),
    url: "#",
    engagement: p.engagement,
    sentiment: p.sentiment,
    narrative: p.narrative,
    region_id: r.id,
    region_conf: 0.85,
    caption: p.caption ?? (p.media && !p.ocr ? p.media.description : null),
    ocr: p.ocr ?? null,
  };
}

function regionsFor(topic: string): MockRegion[] {
  return REGIONS[topic] ?? REGIONS["ai-datacenters"];
}

export function mockTopics(): Topic[] {
  return Object.keys(REGIONS).map((id) => {
    const rs = REGIONS[id];
    const total = rs.reduce((a, r) => a + r.volume, 0);
    const mood = Math.round(rs.reduce((a, r) => a + r.score * r.volume, 0) / total);
    return { id, name: TOPIC_NAMES[id], post_count: total, mood };
  });
}

export function mockGlobe(topic: string): GlobeResponse {
  const rs = regionsFor(topic);
  const max = Math.max(...rs.map((r) => r.volume));
  return {
    topic,
    points: rs.map((r) => ({
      region_id: r.id, name: r.name, lat: r.lat, lon: r.lon,
      score: r.score, volume: r.volume, norm_volume: +(r.volume / max).toFixed(3),
    })),
  };
}

export function mockRegion(topic: string, regionId: string): RegionDetail {
  const rs = regionsFor(topic);
  const r = rs.find((x) => x.id === regionId) ?? rs[0];
  const narratives: Narrative[] = r.narratives.map(([label, share, sentiment]) => ({ label, share, sentiment }));
  return {
    region_id: r.id,
    name: r.name,
    topic,
    score: r.score,
    mood_label: moodLabel(r.score),
    count: r.volume,
    narratives,
    posts: r.posts.map((p, i) => toPost(topic, r, p, i)).sort((a, b) => b.engagement - a.engagement).slice(0, 5),
    trend: buildTrend(r),
    confidence: r.confidence ?? {
      level: r.volume > 2000 ? "high" : r.volume > 1000 ? "medium" : "low",
      note: `Based on ${r.volume.toLocaleString()} posts over 30 days, including photos and video. Location inferred from text, community and image cues.`,
    },
  };
}

export function mockSpread(): SpreadResponse {
  return {
    id: "dance-challenge",
    name: "New dance challenge",
    steps: [
      { region_id: "seoul", hours: 0, note: "Original video posted, 2.1M views in 3 hours", count: 1840, lat: 37.5, lon: 127.0, name: "Seoul" },
      { region_id: "manila", hours: 2, note: "Remixes with local songs, mostly positive", count: 960, lat: 14.6, lon: 121.0, name: "Manila" },
      { region_id: "jakarta", hours: 4, note: "School and office versions trending", count: 1420, lat: -6.2, lon: 106.8, name: "Jakarta" },
      { region_id: "los-angeles", hours: 5, note: "Picked up by creators with large followings", count: 780, lat: 34.0, lon: -118.2, name: "Los Angeles" },
      { region_id: "sao-paulo", hours: 6, note: "Fastest growth right now, 312 new videos per hour", count: 2210, lat: -23.5, lon: -46.6, name: "São Paulo" },
    ],
    arcs: [["seoul", "manila"], ["manila", "jakarta"], ["seoul", "los-angeles"], ["jakarta", "sao-paulo"]],
  };
}

export function mockTrending(): TrendingItem[] {
  return [
    { id: "dance-challenge", name: "Dance challenge jumps to Brazil", category: "Culture", regions: ["seoul", "manila", "jakarta", "sao-paulo"], format: "video", velocity: 3, sentiment: 0.62, count: 7210 },
    { id: "eirgrid-alert", name: "Grid alert screenshots in Ireland", category: "News", regions: ["ireland"], format: "images", velocity: 2, sentiment: -0.58, count: 1880 },
    { id: "battery-fire", name: "Singapore battery-fire clip resurfaces", category: "News", regions: ["singapore", "johor"], format: "video", velocity: 1, sentiment: -0.71, count: 1240 },
    { id: "petrol-meme", name: "\"Me vs the petrol price\" meme", category: "Meme", regions: ["manila", "jakarta"], format: "images", velocity: 2, sentiment: 0.35, count: 2650 },
    { id: "phone-launch", name: "Phone launch mocked in memes", category: "Tech", regions: ["los-angeles", "united-kingdom", "bangalore"], format: "images", velocity: -1, sentiment: -0.22, count: 3120 },
  ];
}

// ---- ask (deterministic) -----------------------------------------------------

export function mockAsk(req: AskRequest): AskResponse {
  const q = req.question.toLowerCase();
  const tool_calls = (calls: [string, Record<string, unknown>][]) => calls.map(([name, args]) => ({ name, args }));

  if (q.includes("viral") || q.includes("trend") || q.includes("spread")) {
    const s = mockSpread();
    return {
      answer: {
        verdict: "Breaking out",
        tone: "positive",
        summary: "A Seoul dance challenge crossed four countries in six hours — and news hasn't caught up.",
        paragraphs: [
          "The fastest-moving thing right now is a dance challenge that started in Seoul and reached Manila within two hours, where creators remixed it with local songs [1].",
          "From there it jumped to Jakarta school and office versions [2], then to Los Angeles creators and São Paulo, which is now growing fastest at over 300 new videos an hour [3].",
          "Elsewhere, Irish grid-alert screenshots are climbing alongside the AI datacenter debate, and a Singapore battery-fire clip is resurfacing.",
        ],
        citations: [
          { n: 1, post_id: "spread-manila", source: "TikTok · Manila", text: "Did the Seoul one but with OPM — barkada version 🔥", url: "#" },
          { n: 2, post_id: "spread-jakarta", source: "TikTok · Jakarta", text: "Versi kantor! Our whole floor learned it during lunch.", url: "#" },
          { n: 3, post_id: "spread-saopaulo", source: "YouTube · São Paulo", text: "Brasil chegou no desafio 🇧🇷 — the best version is ours.", url: "#" },
        ],
        confidence: { level: "medium", note: `Matched ${s.steps.reduce((a, x) => a + x.count, 0).toLocaleString()} videos by audio fingerprint and frames. Mainstream news coverage: none yet.` },
      },
      tool_calls: tool_calls([["get_trending", {}], ["get_spread", { id: s.id }], ["search_posts", { query: "dance challenge", limit: 20 }]]),
    };
  }

  const mentionsIreland = q.includes("ireland");
  if (!mentionsIreland && (q.includes("jakarta") || q.includes("singapore") || q.includes("scooter") || req.topic === "electric-scooters")) {
    const j = mockRegion("electric-scooters", "jakarta");
    const s = mockRegion("electric-scooters", "singapore");
    return {
      answer: {
        verdict: "Split",
        tone: "mixed",
        summary: "Excited in Jakarta, skeptical in Singapore.",
        paragraphs: [
          `Jakarta sits at ${signed(j.score)}: people talk about e-scooters as a money saver and post proud first-ride videos [1], helped by a government subsidy.`,
          `Singapore is at ${signed(s.score)}. The conversation is dominated by fire risk in high-rise flats [2] and footpath safety, much of it in news comment sections [3].`,
          "Singapore's mood dipped after a battery-fire video went viral about 13 days ago and hasn't recovered.",
        ],
        citations: [
          { n: 1, post_id: j.posts[0].id, source: "TikTok · Jakarta", text: j.posts[0].text, url: "#" },
          { n: 2, post_id: s.posts[0].id, source: "Reddit · r/singapore", text: s.posts[0].text, url: "#" },
          { n: 3, post_id: s.posts[2]?.id ?? "x", source: "News comments · Singapore", text: s.posts[2]?.text ?? "", url: "#" },
        ],
        confidence: { level: "medium", note: "5,750 posts across both cities; 38% include photos or video. Some posts translated from Indonesian." },
      },
      tool_calls: tool_calls([
        ["get_region", { topic: "electric-scooters", region_id: "jakarta" }],
        ["get_region", { topic: "electric-scooters", region_id: "singapore" }],
        ["get_trend", { topic: "electric-scooters", region_id: "singapore", days: 30 }],
      ]),
    };
  }

  // Default: region-focused answer (Ireland unless a region is selected)
  const topic = mentionsIreland ? "ai-datacenters" : req.topic ?? "ai-datacenters";
  const regionId = mentionsIreland
    ? "ireland"
    : req.region_id && regionsFor(topic).some((r) => r.id === req.region_id)
      ? req.region_id
      : topic === "ai-datacenters" ? "ireland" : regionsFor(topic)[0].id;
  const r = mockRegion(topic, regionId);
  const top = r.narratives[0];
  const tone = r.score >= 8 ? "positive" : r.score <= -8 ? "negative" : "mixed";
  const cites = r.posts.slice(0, 3).map((p, i) => ({
    n: i + 1, post_id: p.id, source: `${cap(p.source)} · ${p.community ?? p.author_loc ?? r.name}`, text: p.text, url: p.url,
  }));
  const isIreland = r.region_id === "ireland";
  return {
    answer: {
      verdict: r.mood_label,
      tone,
      summary: isIreland
        ? "Ireland is souring on datacenters because of the power grid."
        : `${r.name} is ${r.mood_label.toLowerCase()} on ${TOPIC_NAMES[topic] ?? topic}, driven by ${top.label.toLowerCase()}.`,
      paragraphs: [
        `${r.name} scores ${signed(r.score)} across ${r.count.toLocaleString()} posts. The biggest narrative is "${top.label}" at ${Math.round(top.share * 100)}% of the conversation [1].`,
        isIreland
          ? "People connect household energy warnings directly to new datacenter approvals; grid-alert screenshots are being shared widely [2]. Water use is the second theme, while a minority point to well-paid local jobs [3]."
          : `Other recurring themes are ${r.narratives.slice(1, 3).map((n) => n.label.toLowerCase()).join(" and ")}${cites[1] ? " [2]" : ""}.`,
        isIreland ? "Sentiment has worsened noticeably over the last 10 days, tracking a run of grid alerts." : "",
      ].filter(Boolean),
      citations: cites,
      confidence: r.confidence,
    },
    tool_calls: tool_calls([
      ["get_globe", { topic }],
      ["get_region", { topic, region_id: r.region_id }],
      ["search_posts", { topic, region_id: r.region_id, limit: 10 }],
    ]),
  };
}

function signed(n: number) {
  return n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "±0";
}
function cap(s: string) {
  return s === "tiktok" ? "TikTok" : s === "youtube" ? "YouTube" : s.charAt(0).toUpperCase() + s.slice(1);
}

// Diverging sentiment scale: orange (neg) -> grey -> blue (pos).
export const NEG = "#FF8A3D";
export const NEU = "#A7B0BD";
export const POS = "#4C9BFF";
export const ACCENT = "#C8F25A";

function hexToRgb(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a: string, b: string, t: number): [number, number, number] {
  const A = hexToRgb(a), B = hexToRgb(b);
  return [0, 1, 2].map((i) => Math.round(A[i] + (B[i] - A[i]) * t)) as [number, number, number];
}

/** score in -100..100 -> rgba string on the diverging scale */
export function scoreColor(score: number, alpha = 1): string {
  const t = Math.max(-1, Math.min(1, score / 50)); // saturate at ±50
  const [r, g, b] = t < 0 ? mix(NEU, NEG, -t) : mix(NEU, POS, t);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** Lighter text colors for big numbers (from mockup). */
export function scoreTextColor(score: number): string {
  return score > 8 ? "#7DB6FF" : score < -8 ? "#FFB27E" : "#C9CFD8";
}

export function sentimentBarColor(s: number): string {
  return s > 0.15 ? POS : s < -0.15 ? NEG : NEU;
}

export function signed(n: number): string {
  return n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "±0";
}

export function moodLabel(score: number): string {
  if (score >= 25) return "Very positive";
  if (score >= 8) return "Positive";
  if (score > -8) return "Mixed";
  if (score > -25) return "Negative";
  return "Very negative";
}

export function compact(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n);
}

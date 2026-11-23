export const clamp = (x: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
export const easeOut = (t: number) => 1 - Math.pow(1 - clamp(t), 3);
export const easeOutBack = (t: number) => {
	const c1 = 1.70158;
	const c3 = c1 + 1;
	const x = clamp(t);
	return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
};

export const hashString = (s: string) => {
	let h = 2166136261;
	for (let i = 0; i < s.length; i++) {
		h = Math.imul(h ^ s.charCodeAt(i), 16777619);
	}
	return h >>> 0;
};

/** Deterministic 0..1 value for an integer seed (mulberry32 step). */
export const rand01 = (seed: number) => {
	let t = (seed + 0x6d2b79f5) | 0;
	t = Math.imul(t ^ (t >>> 15), t | 1);
	t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
	return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** Smooth value noise in -1..1, deterministic per seed. */
export const noise1 = (t: number, seed: number) => {
	const i = Math.floor(t);
	const f = t - i;
	const a = rand01(seed * 7919 + i);
	const b = rand01(seed * 7919 + i + 1);
	return lerp(a, b, f * f * (3 - 2 * f)) * 2 - 1;
};

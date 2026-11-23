import {Color} from 'three';

/** Shift lightness of a hex color by `amount` (-1..1). */
export const shade = (hex: string, amount: number) => {
	const c = new Color(hex);
	const hsl = {h: 0, s: 0, l: 0};
	c.getHSL(hsl);
	c.setHSL(hsl.h, hsl.s, Math.min(1, Math.max(0, hsl.l + amount)));
	return `#${c.getHexString()}`;
};

/** A readable, bright highlight color derived from a character's outfit color. */
export const highlightColor = (hex: string) => {
	const c = new Color(hex);
	const hsl = {h: 0, s: 0, l: 0};
	c.getHSL(hsl);
	c.setHSL(hsl.h, Math.max(0.55, hsl.s), Math.max(0.62, Math.min(0.72, hsl.l + 0.2)));
	return `#${c.getHexString()}`;
};

export const OUTLINE = '#1d1720';
export const MOUTH_DARK = '#4a1620';
export const TONGUE = '#e0707a';
export const EYE_DARK = '#1d1720';

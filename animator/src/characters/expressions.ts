export type EyeShape = 'normal' | 'wide' | 'squint' | 'halflid' | 'happy' | 'closed';
export type MouthBase = 'smile' | 'bigsmile' | 'frown' | 'flat' | 'smirk' | 'o' | 'wavy' | 'grin';

export type Expression = {
	/** Brow angle in radians; positive raises the inner end (worried), negative lowers it (angry). */
	browInner: number;
	/** Extra raise of the brow on the +x side (for one-brow-up looks). */
	browAsym: number;
	browY: number;
	eye: EyeShape;
	eyeScale: number;
	mouth: MouthBase;
	blush: number;
	sweat: boolean;
	tears: boolean;
	anger: boolean;
};

const base: Expression = {
	browInner: 0,
	browAsym: 0,
	browY: 0,
	eye: 'normal',
	eyeScale: 1,
	mouth: 'smile',
	blush: 0,
	sweat: false,
	tears: false,
	anger: false,
};

export const EXPRESSIONS: Record<string, Expression> = {
	neutral: {...base, mouth: 'flat'},
	happy: {...base, browY: 0.04, mouth: 'smile', blush: 0.35},
	laughing: {...base, browY: 0.06, eye: 'happy', mouth: 'bigsmile', blush: 0.5},
	sad: {...base, browInner: 0.35, browY: -0.02, eyeScale: 0.9, mouth: 'frown'},
	crying: {...base, browInner: 0.45, eye: 'closed', mouth: 'wavy', tears: true},
	angry: {...base, browInner: -0.45, browY: -0.05, eye: 'squint', mouth: 'grin', anger: true},
	shocked: {...base, browY: 0.12, eye: 'wide', eyeScale: 1.25, mouth: 'o'},
	smug: {...base, browAsym: 0.1, browInner: -0.1, eye: 'halflid', mouth: 'smirk'},
	nervous: {...base, browInner: 0.3, mouth: 'wavy', sweat: true},
	confused: {...base, browAsym: 0.12, browInner: 0.1, mouth: 'wavy', eyeScale: 0.95},
	annoyed: {...base, browInner: -0.2, browY: -0.04, eye: 'halflid', mouth: 'flat'},
	embarrassed: {...base, browInner: 0.3, eye: 'happy', mouth: 'wavy', blush: 0.9, sweat: true},
};

/** How a listener reacts to the speaker's emotion. */
const REACTIONS: Record<string, string> = {
	angry: 'nervous',
	shocked: 'shocked',
	laughing: 'happy',
	happy: 'happy',
	smug: 'annoyed',
	sad: 'sad',
	crying: 'sad',
	nervous: 'confused',
	confused: 'confused',
	annoyed: 'nervous',
	embarrassed: 'happy',
	neutral: 'neutral',
};

export const expressionFor = (emotion: string) => EXPRESSIONS[emotion] ?? EXPRESSIONS.neutral;
export const reactionTo = (emotion: string) => REACTIONS[emotion] ?? 'neutral';

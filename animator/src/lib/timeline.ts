import type {MouthShape, Timeline, TimelineBeat} from '../types';

export const beatsOfScene = (tl: Timeline, sceneIndex: number) => tl.beats.filter((b) => b.scene === sceneIndex);

/**
 * Index of the beat that "owns" time t. Ownership switches halfway through the silence
 * between two beats, so cuts land just before the next line starts.
 */
export const activeBeatIndex = (beats: TimelineBeat[], t: number) => {
	if (beats.length === 0) {
		return -1;
	}
	for (let i = 0; i < beats.length - 1; i++) {
		const boundary = (beats[i].end + beats[i + 1].start) / 2;
		if (t < boundary) {
			return i;
		}
	}
	return beats.length - 1;
};

export const segmentStart = (beats: TimelineBeat[], i: number, sceneStart: number) =>
	i <= 0 ? sceneStart : (beats[i - 1].end + beats[i].start) / 2;

export const segmentEnd = (beats: TimelineBeat[], i: number, sceneEnd: number) =>
	i >= beats.length - 1 ? sceneEnd : (beats[i].end + beats[i + 1].start) / 2;

/** Mouth shape at time t while `beat` is being spoken, or null when silent. */
export const mouthAt = (beat: TimelineBeat | undefined, t: number): MouthShape | null => {
	if (!beat || t < beat.start || t > beat.end || beat.mouth.length === 0) {
		return null;
	}
	let lo = 0;
	let hi = beat.mouth.length - 1;
	if (t < beat.mouth[0][0]) {
		return 'rest';
	}
	while (lo < hi) {
		const mid = (lo + hi + 1) >> 1;
		if (beat.mouth[mid][0] <= t) {
			lo = mid;
		} else {
			hi = mid - 1;
		}
	}
	return beat.mouth[lo][1];
};

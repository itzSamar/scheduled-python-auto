import type {TownProps} from './types';

const sets = ['store', 'crowd', 'mayor', 'boom', 'aftermath'] as const;

/** Stand-in timing so a still can be rendered before the voice exists. */
export const defaultTownProps: TownProps = {
	shots: sets.map((set, i) => ({set, start: i * 4, end: i * 4 + 4})),
	words: [
		{text: 'In', start: 0.2, end: 0.5},
		{text: 'this', start: 0.5, end: 0.85},
		{text: 'town,', start: 0.85, end: 1.3},
		{text: 'GTA', start: 1.4, end: 1.8},
		{text: '6', start: 1.8, end: 2.1},
		{text: 'sold', start: 2.15, end: 2.5},
		{text: 'out.', start: 2.5, end: 3.0},
	],
};

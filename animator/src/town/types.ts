export type SetId = 'store' | 'crowd' | 'mayor' | 'boom' | 'aftermath';

export type TownWord = {text: string; start: number; end: number};

export type TownShot = {set: SetId; start: number; end: number};

export type TownProps = {
	shots: TownShot[];
	words: TownWord[];
};

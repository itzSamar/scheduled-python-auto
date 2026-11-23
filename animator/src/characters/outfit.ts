import {shade} from '../lib/colors';
import type {Character} from '../types';

export type OutfitColors = {
	torso: string;
	sleeve: string;
	forearm: string;
	pants: string | null;
	shoes: string;
	accent: string;
	hair: string;
};

/** Derived palette for a character's clothes. */
export const outfitColors = (c: Character): OutfitColors => {
	const {outfit, outfitColor, skin, hairColor} = c.look;
	const older = ['30s', '40s', '50s', 'elderly'].includes(c.age);
	const pants = outfit === 'dress' ? null : outfit === 'suit' ? shade(outfitColor, -0.06) : older ? '#4b4f58' : '#3d4f7c';
	const shortSleeves = outfit === 'tshirt' || outfit === 'dress' || outfit === 'apron';
	const torso = outfit === 'apron' ? '#f4efe6' : outfitColor;
	return {
		torso,
		sleeve: outfit === 'apron' ? '#f4efe6' : outfitColor,
		forearm: shortSleeves ? skin : outfit === 'apron' ? '#f4efe6' : outfitColor,
		pants,
		shoes: '#2b2a33',
		accent: shade(outfitColor, -0.18),
		hair: hairColor,
	};
};

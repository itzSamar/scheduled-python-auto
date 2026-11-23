export type MouthShape = 'rest' | 'closed' | 'mid' | 'open' | 'wide' | 'round' | 'teeth';
export type RenderStyle = '2d' | '3d' | 'mixed';
export type SceneStyle = '2d' | '3d';

export type Look = {
	hair: string;
	hairColor: string;
	skin: string;
	outfit: string;
	outfitColor: string;
	accessory: string;
};

export type Character = {
	id: string;
	name: string;
	gender: 'female' | 'male';
	age: string;
	voiceTone: string;
	look: Look;
};

export type Beat = {
	speaker: string;
	text: string;
	emotion: string;
	action: string;
	camera: string;
};

export type Scene = {
	location: string;
	timeOfDay: 'day' | 'evening' | 'night';
	onscreen: string[];
	beats: Beat[];
};

export type Screenplay = {
	title: string;
	mood: string;
	characters: Character[];
	scenes: Scene[];
};

export type Word = {text: string; start: number; end: number};

export type TimelineBeat = {
	index: number;
	scene: number;
	speaker: string;
	character: string;
	narration: boolean;
	start: number;
	end: number;
	text: string;
	emotion: string;
	action: string;
	camera: string;
	words: Word[];
	mouth: [number, MouthShape][];
};

export type Timeline = {
	sampleRate: number;
	duration: number;
	scenes: {index: number; start: number; end: number}[];
	beats: TimelineBeat[];
};

export type EpisodeProps = {
	screenplay: Screenplay;
	timeline: Timeline;
	style: RenderStyle;
	audioSrc: string | null;
	subreddit?: string;
	seed: number;
};

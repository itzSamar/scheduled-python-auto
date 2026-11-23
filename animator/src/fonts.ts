import {useEffect, useState} from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';

export const FONT_FAMILY = 'StoryHeavy';
export const FONT_STACK = `${FONT_FAMILY}, 'Arial Black', 'Helvetica Neue', sans-serif`;

let loading: Promise<void> | null = null;

const loadFont = () => {
	if (!loading) {
		const face = new FontFace(FONT_FAMILY, `url('${staticFile('fonts/Volkswagen-Heavy.otf')}') format('opentype')`);
		loading = face
			.load()
			.then((f) => {
				document.fonts.add(f);
			})
			.catch((err) => {
				console.warn('Caption font failed to load, using fallback', err);
			});
	}
	return loading;
};

/** Blocks rendering until the caption font is ready. */
export const useStoryFont = () => {
	const [handle] = useState(() => delayRender('Loading caption font'));
	useEffect(() => {
		loadFont().then(() => continueRender(handle));
	}, [handle]);
};

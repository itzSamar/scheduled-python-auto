// Renders several stills from one bundle: node scripts/stills.mjs <outDir> <frame> [frame...] [--props=file.json]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const propsArg = args.find((a) => a.startsWith('--props='));
const [outDir, ...frames] = args.filter((a) => !a.startsWith('--'));
const inputProps = propsArg ? JSON.parse(fs.readFileSync(propsArg.slice(8), 'utf8')) : undefined;

fs.mkdirSync(outDir, {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public')});
const composition = await selectComposition({serveUrl, id: 'StoryShort', inputProps, chromiumOptions: {gl: 'angle'}});
for (const f of frames.map(Number)) {
	const output = path.join(outDir, `f${String(f).padStart(5, '0')}.png`);
	await renderStill({serveUrl, composition, frame: f, output, inputProps, chromiumOptions: {gl: 'angle'}, scale: 0.5});
	console.log(output);
}

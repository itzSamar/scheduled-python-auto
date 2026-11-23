import {ThreeCanvas} from '@remotion/three';
import {useFrame, useThree} from '@react-three/fiber';
import React, {useMemo, useRef} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import type {OrthographicCamera, PerspectiveCamera} from 'three';
import {OutlineEffect} from 'three/examples/jsm/effects/OutlineEffect.js';
import {Character2D} from '../characters/Character2D';
import {Character3D} from '../characters/Character3D';
import {characterState, layoutSlots} from '../characters/state';
import {FOV_3D, framingAt, perspectivePose, type Framing} from '../director/camera';
import {hashString} from '../lib/math';
import {activeBeatIndex, beatsOfScene, segmentEnd, segmentStart} from '../lib/timeline';
import {buildSet, type TimeOfDay} from '../sets/locations';
import {SetView, propLift} from '../sets/SetView';
import type {EpisodeProps, SceneStyle} from '../types';

const CameraRig: React.FC<{framing: Framing; mode: SceneStyle}> = ({framing, mode}) => {
	const ref = useRef(framing);
	ref.current = framing;
	useFrame((state) => {
		const fr = ref.current;
		if (mode === '2d') {
			const cam = state.camera as OrthographicCamera;
			cam.position.set(fr.x + fr.shakeX, fr.y + fr.shakeY, 30);
			cam.rotation.set(0, 0, fr.roll);
			cam.zoom = state.size.height / fr.h;
			cam.updateProjectionMatrix();
			return;
		}
		const cam = state.camera as PerspectiveCamera;
		const pose = perspectivePose(fr);
		cam.position.set(...pose.position);
		cam.up.set(Math.sin(pose.roll), Math.cos(pose.roll), 0);
		cam.lookAt(...pose.target);
		cam.updateProjectionMatrix();
	}, 0);
	return null;
};

/** Takes over rendering (priority > 0) to draw toon ink lines with an inverted-hull pass. */
const OutlineRenderer: React.FC = () => {
	const gl = useThree((s) => s.gl);
	const effect = useMemo(
		() => new OutlineEffect(gl, {defaultThickness: 0.0035, defaultColor: [0.11, 0.09, 0.12], defaultAlpha: 1, defaultKeepAlive: true}),
		[gl],
	);
	useFrame((state) => {
		effect.render(state.scene, state.camera);
	}, 1);
	return null;
};

type Light = {key: string; keyI: number; amb: string; ambI: number; sky: string; ground: string; hemiI: number};

const LIGHTS: Record<TimeOfDay, Light> = {
	day: {key: '#fff6e8', keyI: 2.0, amb: '#ffffff', ambI: 0.7, sky: '#dff1ff', ground: '#b9a68f', hemiI: 0.45},
	evening: {key: '#ffc89a', keyI: 1.9, amb: '#ffe0c8', ambI: 0.62, sky: '#ffb38a', ground: '#5b4a6b', hemiI: 0.5},
	night: {key: '#b3c0ff', keyI: 1.5, amb: '#8a94d0', ambI: 0.95, sky: '#7684d6', ground: '#2a2340', hemiI: 0.5},
};
/** Indoors at night the room lights are on. */
const INDOOR_NIGHT: Light = {key: '#ffe2b8', keyI: 1.8, amb: '#ffeedd', ambI: 0.82, sky: '#fff1dc', ground: '#6b5a4a', hemiI: 0.45};

const tint2d = (tod: TimeOfDay, exterior: boolean) => {
	if (tod === 'evening') {
		return {color: '#ff8a4c', opacity: 0.12};
	}
	if (tod === 'night') {
		return exterior ? {color: '#1b2a6b', opacity: 0.24} : {color: '#ffb36b', opacity: 0.08};
	}
	return {color: '#000000', opacity: 0};
};

export const SceneView: React.FC<{episode: EpisodeProps; sceneIndex: number; mode: SceneStyle}> = ({episode, sceneIndex, mode}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const {screenplay, timeline, seed} = episode;
	const scene = screenplay.scenes[sceneIndex];
	const sceneTl = timeline.scenes[sceneIndex];
	const t = sceneTl.start + frame / fps;
	const tod = (scene.timeOfDay ?? 'day') as TimeOfDay;
	const sceneSeed = (seed + sceneIndex * 101 + (hashString(scene.location) % 97)) | 0;

	const spec = useMemo(() => buildSet(scene.location, tod, sceneSeed), [scene.location, tod, sceneSeed]);
	const beats = useMemo(() => beatsOfScene(timeline, sceneIndex), [timeline, sceneIndex]);
	const slots = useMemo(() => layoutSlots(screenplay.characters, scene.onscreen, spec.seated), [screenplay.characters, scene.onscreen, spec.seated]);

	const bi = activeBeatIndex(beats, t);
	const framing = framingAt(
		beats[bi],
		slots,
		t,
		segmentStart(beats, bi, sceneTl.start),
		segmentEnd(beats, bi, sceneTl.end),
		sceneTl.start,
		sceneSeed % 1000,
	);

	const states = [...slots.entries()].map(([id, slot]) => {
		const character = screenplay.characters.find((c) => c.id === id)!;
		return characterState(character, slot, slots, beats, t, sceneTl.start);
	});
	const light = tod === 'night' && !spec.exterior ? INDOOR_NIGHT : LIGHTS[tod];
	const tint = tint2d(tod, spec.exterior);
	const is3d = mode === '3d';

	return (
		<AbsoluteFill>
			<ThreeCanvas
				key={mode}
				width={width}
				height={height}
				orthographic={!is3d}
				flat
				gl={{antialias: true, preserveDrawingBuffer: true}}
				camera={is3d ? {fov: FOV_3D, near: 0.1, far: 120, position: [0, 1.2, 7]} : {near: 0.1, far: 120, position: [0, 1, 30], zoom: 400}}
			>
				<color attach="background" args={[spec.sky]} />
				{is3d && spec.exterior ? <fog attach="fog" args={[spec.sky, 16, 42]} /> : null}
				<CameraRig framing={framing} mode={mode} />
				<OutlineRenderer />
				{is3d ? (
					<>
						<ambientLight color={light.amb} intensity={light.ambI} />
						<hemisphereLight args={[light.sky, spec.exterior ? spec.hemiGround : light.ground, light.hemiI]} />
						<directionalLight color={light.key} intensity={light.keyI} position={[3, 6, 5]} />
					</>
				) : null}
				<SetView spec={spec} mode={mode} t={t - sceneTl.start} camX={framing.x} />
				{states.map((s) =>
					is3d ? <Character3D key={s.character.id} state={s} /> : <Character2D key={s.character.id} state={s} yShift={propLift(s.slot.z)} />,
				)}
			</ThreeCanvas>
			{!is3d && tint.opacity > 0 ? <AbsoluteFill style={{backgroundColor: tint.color, opacity: tint.opacity, mixBlendMode: 'multiply'}} /> : null}
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.38) 100%)'}} />
		</AbsoluteFill>
	);
};

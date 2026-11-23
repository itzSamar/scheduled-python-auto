import {ThreeCanvas} from '@remotion/three';
import React, {useMemo} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {CanvasTexture, Color, MeshBasicMaterial, ShaderMaterial, SRGBColorSpace} from 'three';
import {Avatar, plastic} from './roblox/avatar';
import type {SetId} from './types';

const signCache = new Map<string, MeshBasicMaterial>();

const signMaterial = (text: string, bg: string, fg: string) => {
	const key = `${text}|${bg}|${fg}`;
	const hit = signCache.get(key);
	if (hit) {
		return hit;
	}
	const canvas = document.createElement('canvas');
	canvas.width = 512;
	canvas.height = 180;
	const g = canvas.getContext('2d');
	if (!g) {
		throw new Error('canvas unavailable');
	}
	g.fillStyle = bg;
	g.fillRect(0, 0, 512, 180);
	g.fillStyle = fg;
	g.textAlign = 'center';
	g.textBaseline = 'middle';
	let size = 84;
	g.font = `900 ${size}px Arial`;
	while (g.measureText(text).width > 470 && size > 32) {
		size -= 4;
		g.font = `900 ${size}px Arial`;
	}
	g.fillText(text, 256, 94);
	const tex = new CanvasTexture(canvas);
	tex.colorSpace = SRGBColorSpace;
	const mat = new MeshBasicMaterial({map: tex});
	mat.dispose = () => undefined;
	tex.dispose = () => undefined;
	signCache.set(key, mat);
	return mat;
};

const Sign: React.FC<{text: string; bg: string; fg: string; w: number; h: number; position: [number, number, number]; rot?: [number, number, number]}> = ({
	text,
	bg,
	fg,
	w,
	h,
	position,
	rot = [0, 0, 0],
}) => (
	<group position={position} rotation={rot}>
		<mesh material={plastic(bg, 0.5)} castShadow>
			<boxGeometry args={[w, h, 0.06]} />
		</mesh>
		<mesh position={[0, 0, 0.035]} scale={[w * 0.9, h * 0.72, 1]} material={signMaterial(text, bg, fg)}>
			<planeGeometry args={[1, 1]} />
		</mesh>
	</group>
);

const skyMat = (hot: boolean) => {
	const mat = new ShaderMaterial({
		side: 1,
		depthWrite: false,
		uniforms: {
			top: {value: new Color(hot ? '#ff6a2a' : '#79c8ff')},
			bottom: {value: new Color(hot ? '#ffd7a8' : '#e7f5ff')},
		},
		vertexShader: `varying vec3 v; void main(){ v = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
		fragmentShader: `varying vec3 v; uniform vec3 top; uniform vec3 bottom; void main(){ float h = clamp(normalize(v).y * 0.55 + 0.45, 0.0, 1.0); gl_FragColor = vec4(mix(bottom, top, h), 1.0); }`,
	});
	mat.side = 2;
	return mat;
};

const House: React.FC<{x: number; z: number; wall: string; roof: string}> = ({x, z, wall, roof}) => (
	<group position={[x, 0, z]}>
		<mesh position={[0, 0.85, 0]} material={plastic(wall, 0.6)} castShadow receiveShadow>
			<boxGeometry args={[2.4, 1.7, 2.1]} />
		</mesh>
		<mesh position={[0, 1.95, 0]} rotation={[0, Math.PI / 4, 0]} material={plastic(roof, 0.55)} castShadow>
			<coneGeometry args={[1.9, 1.0, 4]} />
		</mesh>
		<mesh position={[-0.5, 1.05, 1.06]} material={plastic('#b9e6ff', 0.15)}>
			<boxGeometry args={[0.55, 0.5, 0.04]} />
		</mesh>
		<mesh position={[0.5, 0.55, 1.06]} material={plastic('#6b4226', 0.6)}>
			<boxGeometry args={[0.5, 0.95, 0.05]} />
		</mesh>
	</group>
);

const Shop: React.FC<{fallen?: boolean}> = ({fallen}) => (
	<group position={[0.1, fallen ? 0.15 : 0, -3.3]} rotation={fallen ? [0, 0, 0.4] : [0, 0, 0]}>
		<mesh position={[0, 1.25, 0]} material={plastic('#f4d35e', 0.55)} castShadow receiveShadow>
			<boxGeometry args={[3.3, 2.5, 2.2]} />
		</mesh>
		<mesh position={[0, 2.6, 0]} material={plastic('#e23d4a', 0.5)} castShadow>
			<boxGeometry args={[3.5, 0.22, 2.4]} />
		</mesh>
		<Sign text="GTA 6" bg="#161616" fg="#f6d34d" w={2.1} h={0.46} position={[0, 2.15, 1.12]} />
		<Sign text="SOLD OUT" bg="#e23d4a" fg="#ffffff" w={2.1} h={0.42} position={[0, 1.6, 1.14]} />
	</group>
);

const Ground: React.FC<{hot: boolean}> = ({hot}) => (
	<group>
		<mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow material={plastic(hot ? '#8aa15a' : '#5ec04c', 0.95)}>
			<planeGeometry args={[60, 60]} />
		</mesh>
		<mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, -4]} receiveShadow material={plastic('#3e424a', 0.85)}>
			<planeGeometry args={[2.8, 28]} />
		</mesh>
		{Array.from({length: 8}).map((_, i) => (
			<mesh key={i} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 1.2 - i * 2.4]} material={plastic('#f4f4f4', 0.6)}>
				<planeGeometry args={[0.12, 0.7]} />
			</mesh>
		))}
	</group>
);

const Cloud: React.FC<{local: number}> = ({local}) => {
	const puff = plastic('#fffaf4', 0.7);
	const stem = plastic('#ffe8d2', 0.65);
	const rise = Math.min(local * 0.35, 0.4);
	return (
		<group position={[0, rise, -1.2]}>
			<mesh position={[0, 1.3, 0]} scale={[0.85, 2.1, 0.85]} material={stem} castShadow>
				<sphereGeometry args={[0.7, 24, 18]} />
			</mesh>
			<mesh position={[0, 3.15, 0]} material={puff} castShadow>
				<sphereGeometry args={[1.55, 28, 20]} />
			</mesh>
			<mesh position={[-0.95, 2.7, 0.2]} material={puff} castShadow>
				<sphereGeometry args={[0.85, 22, 16]} />
			</mesh>
			<mesh position={[1.0, 2.65, 0.1]} material={puff} castShadow>
				<sphereGeometry args={[0.9, 22, 16]} />
			</mesh>
			<mesh position={[0, 3.7, -0.1]} material={puff}>
				<sphereGeometry args={[0.7, 18, 14]} />
			</mesh>
		</group>
	);
};

const Stage: React.FC<{set: SetId; local: number}> = ({set, local}) => {
	const hot = set === 'boom' || set === 'aftermath';
	return (
		<group>
			<Ground hot={hot} />
			{set === 'aftermath' ? (
				<>
					<Shop fallen />
					<mesh position={[-1.4, 0.25, -1.2]} rotation={[0, 0.2, 0.9]} material={plastic('#ffafcc', 0.6)} castShadow>
						<boxGeometry args={[1.4, 0.8, 1.1]} />
					</mesh>
					<mesh position={[1.6, 0.3, -1.6]} rotation={[0.2, 0, -0.6]} material={plastic('#8ecae6', 0.6)} castShadow>
						<boxGeometry args={[1.2, 0.7, 1]} />
					</mesh>
					<Avatar prompt="smirk, spiky brown hair, yellow shirt, blue jeans" position={[0, 0, 1.15]} anim="sit" />
				</>
			) : (
				<>
					{set !== 'boom' ? <Shop /> : null}
					<House x={-4.4} z={-6.5} wall="#ffafcc" roof="#d00000" />
					<House x={4.6} z={-7} wall="#8ecae6" roof="#023047" />
				</>
			)}
			{set === 'store' ? (
				<>
					<Avatar prompt="smile, spiky brown hair, yellow shirt, blue jeans" position={[-0.55, 0, 0.7]} anim="idle" />
					<Avatar prompt="smile, long brown hair, teal shirt, dark pants" position={[0.58, 0, 0.45]} anim="idle" phase={0.6} />
				</>
			) : null}
			{set === 'crowd' ? (
				<>
					<mesh position={[0, 0.55, 0.15]} material={plastic('#222', 0.4)} castShadow>
						<boxGeometry args={[0.34, 0.46, 0.08]} />
					</mesh>
					<Avatar prompt="mad, side brown hair, red shirt, jeans" position={[-0.7, 0, 1.05]} rotationY={0.25} anim="reach" />
					<Avatar prompt="shocked, long black hair, pink shirt, dark pants" position={[0.75, 0, 1.0]} rotationY={-0.3} anim="reach" phase={0.4} />
					<Avatar prompt="mad, spiky black hair, green shirt, blue jeans" position={[-0.15, 0, 1.55]} anim="reach" phase={0.8} />
				</>
			) : null}
			{set === 'mayor' ? (
				<>
					<mesh position={[0, 0.55, 0.15]} material={plastic('#d9d9d9', 0.45)} castShadow receiveShadow>
						<boxGeometry args={[1.5, 0.7, 0.7]} />
					</mesh>
					<mesh position={[0, 1.05, 0.35]} material={plastic('#e23d4a', 0.28)} castShadow>
						<cylinderGeometry args={[0.28, 0.28, 0.16, 24]} />
					</mesh>
					<mesh position={[0, 1.16, 0.35]} material={plastic('#ff4d4d', 0.22)}>
						<cylinderGeometry args={[0.2, 0.2, 0.1, 24]} />
					</mesh>
					<Avatar prompt="mad, short gray hair, white shirt, black pants" position={[0, 0, -0.55]} anim="reach" />
				</>
			) : null}
			{set === 'boom' ? (
				<>
					<Cloud local={local} />
					<Avatar prompt="shocked, spiky brown hair, yellow shirt, blue jeans" position={[-0.45, 0, 1.7]} anim="cheer" />
					<Avatar prompt="shocked, long brown hair, teal shirt, dark pants" position={[0.5, 0, 1.55]} anim="cheer" phase={0.5} />
				</>
			) : null}
		</group>
	);
};

const CAM: Record<SetId, {p: [number, number, number]; l: [number, number, number]}> = {
	store: {p: [0, 1.7, 6.6], l: [0, 1.25, -0.8]},
	crowd: {p: [0, 1.65, 6.2], l: [0, 1.15, 0.1]},
	mayor: {p: [0, 1.7, 5.4], l: [0, 1.25, -0.3]},
	boom: {p: [0, 1.35, 7.2], l: [0, 2.4, -0.8]},
	aftermath: {p: [0.2, 1.55, 5.8], l: [0, 0.95, -0.2]},
};

export const TownScene: React.FC<{set: SetId}> = ({set}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const local = frame / fps;
	const hot = set === 'boom' || set === 'aftermath';
	const sky = useMemo(() => skyMat(hot), [hot]);
	const cam = CAM[set];
	return (
		<AbsoluteFill>
			<ThreeCanvas
				width={width}
				height={height}
				shadows
				flat
				gl={{antialias: true, preserveDrawingBuffer: true}}
				camera={{fov: 42, near: 0.1, far: 80, position: cam.p}}
				onCreated={({camera}) => {
					camera.lookAt(cam.l[0], cam.l[1], cam.l[2]);
				}}
			>
				<mesh scale={50} material={sky}>
					<sphereGeometry args={[1, 24, 16]} />
				</mesh>
				<hemisphereLight args={[hot ? '#ffd0a8' : '#e7f4ff', hot ? '#6d5a3a' : '#6aaa55', 0.65]} />
				<ambientLight intensity={0.35} />
				<directionalLight
					position={[5, 9, 4]}
					intensity={2.1}
					color={hot ? '#ffc089' : '#fff6e4'}
					castShadow
					shadow-mapSize-width={1024}
					shadow-mapSize-height={1024}
					shadow-camera-near={0.5}
					shadow-camera-far={30}
					shadow-camera-left={-8}
					shadow-camera-right={8}
					shadow-camera-top={8}
					shadow-camera-bottom={-8}
				/>
				<Stage set={set} local={local} />
			</ThreeCanvas>
		</AbsoluteFill>
	);
};

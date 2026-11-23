import {RoundedBoxGeometry} from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import {
	BoxGeometry,
	BufferGeometry,
	CapsuleGeometry,
	CircleGeometry,
	ConeGeometry,
	CylinderGeometry,
	SphereGeometry,
	TorusGeometry,
	Color,
	DataTexture,
	DoubleSide,
	Material,
	MeshBasicMaterial,
	MeshToonMaterial,
	NearestFilter,
	RedFormat,
	RingGeometry,
	Shape,
	ShapeGeometry,
} from 'three';

// Geometries and materials are cached for the lifetime of the render tab; frames re-render
// React every tick and must not allocate new GPU resources each time.
const geoCache = new Map<string, BufferGeometry>();
const matCache = new Map<string, Material>();

// R3F disposes geometry/material props when a mesh unmounts, but cached objects are shared
// by other meshes and canvases. GPU copies are freed when each canvas loses its context.
const keepAlive = <T extends {dispose: () => void}>(o: T): T => {
	o.dispose = () => undefined;
	return o;
};

const cachedGeo = (key: string, make: () => BufferGeometry) => {
	let g = geoCache.get(key);
	if (!g) {
		g = keepAlive(make());
		geoCache.set(key, g);
	}
	return g;
};

const cachedMat = <T extends Material>(key: string, make: () => T): T => {
	let m = matCache.get(key) as T | undefined;
	if (!m) {
		m = keepAlive(make());
		matCache.set(key, m);
	}
	return m;
};

const r2 = (x: number) => Math.round(x * 200) / 200;

/** Unit-diameter circle; scale the mesh to get ellipses. */
export const circleGeo = () => cachedGeo('circle', () => new CircleGeometry(0.5, 48));

export const halfDiscGeo = () => cachedGeo('halfdisc', () => new CircleGeometry(0.5, 32, Math.PI, Math.PI));

export const roundRectGeo = (w: number, h: number, r: number) => {
	const W = r2(w);
	const H = r2(h);
	const R = Math.min(r2(r), W / 2, H / 2);
	return cachedGeo(`rr:${W}:${H}:${R}`, () => {
		const s = new Shape();
		const x = -W / 2;
		const y = -H / 2;
		s.moveTo(x + R, y);
		s.lineTo(x + W - R, y);
		s.absarc(x + W - R, y + R, R, -Math.PI / 2, 0, false);
		s.lineTo(x + W, y + H - R);
		s.absarc(x + W - R, y + H - R, R, 0, Math.PI / 2, false);
		s.lineTo(x + R, y + H);
		s.absarc(x + R, y + H - R, R, Math.PI / 2, Math.PI, false);
		s.lineTo(x, y + R);
		s.absarc(x + R, y + R, R, Math.PI, Math.PI * 1.5, false);
		return new ShapeGeometry(s, 8);
	});
};

/** Arc stroke; theta measured counter-clockwise from +x. */
export const arcGeo = (radius: number, thickness: number, thetaStart: number, thetaLength: number) =>
	cachedGeo(`arc:${r2(radius)}:${r2(thickness)}:${r2(thetaStart)}:${r2(thetaLength)}`, () =>
		new RingGeometry(radius - thickness / 2, radius + thickness / 2, 32, 1, thetaStart, thetaLength),
	);

export const wavyGeo = (w: number, amp: number, thickness: number) =>
	cachedGeo(`wavy:${r2(w)}:${r2(amp)}:${r2(thickness)}`, () => {
		const s = new Shape();
		const steps = 24;
		const top: [number, number][] = [];
		const bottom: [number, number][] = [];
		for (let i = 0; i <= steps; i++) {
			const x = -w / 2 + (w * i) / steps;
			const y = amp * Math.sin((i / steps) * Math.PI * 3);
			top.push([x, y + thickness / 2]);
			bottom.push([x, y - thickness / 2]);
		}
		s.moveTo(top[0][0], top[0][1]);
		top.forEach(([x, y]) => s.lineTo(x, y));
		bottom.reverse().forEach(([x, y]) => s.lineTo(x, y));
		s.closePath();
		return new ShapeGeometry(s);
	});

export const teardropGeo = () =>
	cachedGeo('teardrop', () => {
		const s = new Shape();
		s.moveTo(0, 0.5);
		s.quadraticCurveTo(0.35, 0.0, 0.3, -0.18);
		s.absarc(0, -0.18, 0.3, 0, Math.PI, true);
		s.quadraticCurveTo(-0.35, 0.0, 0, 0.5);
		return new ShapeGeometry(s, 12);
	});

/** Generic closed polygon from points (cached by key). */
export const polyGeo = (key: string, pts: [number, number][]) =>
	cachedGeo(`poly:${key}`, () => {
		const s = new Shape();
		s.moveTo(pts[0][0], pts[0][1]);
		pts.slice(1).forEach(([x, y]) => s.lineTo(x, y));
		s.closePath();
		return new ShapeGeometry(s);
	});

export const capsuleGeo = (radius: number, length: number) =>
	cachedGeo(`cap:${r2(radius)}:${r2(length)}`, () => new CapsuleGeometry(radius, length, 6, 16));

export const sphereGeo = (radius: number, thetaStart = 0, thetaLength = Math.PI, phiStart = 0, phiLength = Math.PI * 2) =>
	cachedGeo(`sph:${r2(radius)}:${r2(thetaStart)}:${r2(thetaLength)}:${r2(phiStart)}:${r2(phiLength)}`, () =>
		new SphereGeometry(radius, 32, 20, phiStart, phiLength, thetaStart, thetaLength),
	);

export const cylGeo = (rTop: number, rBottom: number, h: number, segments = 28, open = false) =>
	cachedGeo(`cyl:${r2(rTop)}:${r2(rBottom)}:${r2(h)}:${segments}:${open}`, () => new CylinderGeometry(rTop, rBottom, h, segments, 1, open));

export const coneGeo = (r: number, h: number, segments = 20) => cachedGeo(`cone:${r2(r)}:${r2(h)}:${segments}`, () => new ConeGeometry(r, h, segments));

export const torusGeo = (r: number, tube: number, arc = Math.PI * 2) =>
	cachedGeo(`tor:${r2(r)}:${r2(tube)}:${r2(arc)}`, () => new TorusGeometry(r, tube, 12, 32, arc));

export const boxGeo = (w: number, h: number, d: number, round = 0) =>
	cachedGeo(`box:${r2(w)}:${r2(h)}:${r2(d)}:${r2(round)}`, () =>
		round > 0 ? new RoundedBoxGeometry(w, h, d, 3, Math.min(round, w / 2, h / 2, d / 2)) : new BoxGeometry(w, h, d),
	);

/** Unlit flat color, never outlined (faces, 2D characters). */
export const flatMat = (color: string, opacity = 1) =>
	cachedMat(`flat:${color}:${opacity}`, () => {
		const m = new MeshBasicMaterial({color: new Color(color), transparent: opacity < 1, opacity, side: DoubleSide});
		m.userData.outlineParameters = {visible: false};
		return m;
	});

/** Unlit flat color that still gets the outline pass (2D sets). */
export const flatOutlinedMat = (color: string) =>
	cachedMat(`flatol:${color}`, () => {
		const m = new MeshBasicMaterial({color: new Color(color)});
		m.userData.outlineParameters = {thickness: 0.0045, color: [0.11, 0.09, 0.12], alpha: 1};
		return m;
	});

let gradient: DataTexture | null = null;
const toonGradient = () => {
	if (!gradient) {
		gradient = new DataTexture(new Uint8Array([120, 190, 255]), 3, 1, RedFormat);
		gradient.minFilter = NearestFilter;
		gradient.magFilter = NearestFilter;
		gradient.needsUpdate = true;
	}
	return gradient;
};

/** Cel-shaded material for 3D characters and sets. */
export const toonMat = (color: string, emissive = 0) =>
	cachedMat(`toon:${color}:${emissive}`, () => {
		const m = new MeshToonMaterial({color: new Color(color), gradientMap: toonGradient()});
		if (emissive > 0) {
			m.emissive = new Color(color);
			m.emissiveIntensity = emissive;
		}
		m.userData.outlineParameters = {thickness: 0.0035, color: [0.11, 0.09, 0.12], alpha: 1};
		return m;
	});

export const toonMatNoOutline = (color: string) =>
	cachedMat(`toonno:${color}`, () => {
		const m = new MeshToonMaterial({color: new Color(color), gradientMap: toonGradient()});
		m.userData.outlineParameters = {visible: false};
		return m;
	});

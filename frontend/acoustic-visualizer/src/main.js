import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const palette = {
  background: 0x0a1922,
  grid: 0x21414a,
  teal: 0x55d9c1,
  cyan: 0x70b9e8,
  amber: 0xe5b56d,
};

export function finiteData(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  if (data.mode === "hero") return true;
  if (data.mode === "waveform") {
    return Number.isFinite(data.duration_seconds)
      && data.duration_seconds > 0
      && Array.isArray(data.points)
      && data.points.length >= 2
      && data.points.length <= 1200
      && data.points.every((point) => Array.isArray(point)
        && point.length === 2
        && point.every(Number.isFinite));
  }
  if (data.mode === "spectrogram") {
    return Array.isArray(data.times)
      && Array.isArray(data.frequencies_hz)
      && Array.isArray(data.magnitude_db)
      && data.times.length >= 2
      && data.frequencies_hz.length >= 2
      && data.times.length <= 128
      && data.frequencies_hz.length <= 64
      && data.times.every(Number.isFinite)
      && data.frequencies_hz.every(Number.isFinite)
      && data.magnitude_db.length === data.frequencies_hz.length
      && data.magnitude_db.every((row) => Array.isArray(row)
        && row.length === data.times.length
        && row.every(Number.isFinite));
  }
  return false;
}

function drawFallback(canvas, data, message) {
  let context = canvas.getContext("2d");
  if (!context) {
    const replacement = canvas.cloneNode(false);
    canvas.replaceWith(replacement);
    canvas = replacement;
    context = canvas.getContext("2d");
  }
  if (!context) {
    return false;
  }
  canvas.dataset.renderMode = "2d";
  const bounds = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.max(1, Math.round(bounds.width * ratio));
  canvas.height = Math.max(1, Math.round(bounds.height * ratio));
  context.scale(ratio, ratio);
  context.fillStyle = "#0a1922";
  context.fillRect(0, 0, bounds.width, bounds.height);
  context.strokeStyle = "#21414a";
  context.lineWidth = 1;
  for (let y = 24; y < bounds.height; y += 32) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(bounds.width, y);
    context.stroke();
  }
  context.strokeStyle = "#55d9c1";
  context.lineWidth = 1.8;
  if (data?.mode === "spectrogram") {
    const rows = data.magnitude_db;
    const cellWidth = bounds.width / data.times.length;
    const cellHeight = bounds.height / rows.length;
    rows.forEach((row, frequencyIndex) => row.forEach((value, timeIndex) => {
      const shade = Math.max(0, Math.min(1, (value + 90) / 90));
      const hue = 190 - 25 * shade;
      context.fillStyle = `hsl(${hue}, ${42 + 25 * shade}%, ${10 + 44 * shade}%)`;
      context.fillRect(
        timeIndex * cellWidth,
        bounds.height - (frequencyIndex + 1) * cellHeight,
        Math.ceil(cellWidth),
        Math.ceil(cellHeight),
      );
    }));
  } else if (data?.mode === "waveform" || data?.mode === "hero") {
    const points = data.mode === "waveform"
      ? data.points
      : Array.from({ length: 240 }, (_, index) => [index / 239, Math.sin(index / 18) * Math.exp(-index / 480)]);
    context.beginPath();
    points.forEach((point, index) => {
      const xValue = data.mode === "waveform" ? point[0] / (data.duration_seconds || 1) : point[0];
      const yValue = point[1];
      const px = 16 + xValue * (bounds.width - 32);
      const py = bounds.height / 2 - yValue * bounds.height * 0.36;
      if (index === 0) context.moveTo(px, py);
      else context.lineTo(px, py);
    });
    context.stroke();
  }
  const notice = document.getElementById("voxneuro-fallback-note");
  if (notice) notice.textContent = message;
  return canvas;
}

function addAxisLine(scene, start, end, color) {
  const geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(...start),
    new THREE.Vector3(...end),
  ]);
  const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color }));
  scene.add(line);
}

function makeHero(scene) {
  const points = [];
  const count = 360;
  for (let index = 0; index < count; index += 1) {
    const u = index / (count - 1);
    const x = (u - 0.5) * 15;
    const envelope = 0.75 + 0.25 * Math.sin(Math.PI * u);
    const y = Math.sin(u * Math.PI * 8) * envelope * 1.5;
    const z = Math.cos(u * Math.PI * 4) * 0.55;
    points.push(new THREE.Vector3(x, y, z));
  }
  const curve = new THREE.CatmullRomCurve3(points);
  const tube = new THREE.TubeGeometry(curve, 520, 0.035, 7, false);
  const material = new THREE.MeshStandardMaterial({
    color: palette.teal,
    emissive: 0x123c37,
    emissiveIntensity: 0.8,
    metalness: 0.22,
    roughness: 0.36,
  });
  scene.add(new THREE.Mesh(tube, material));
  const particles = [];
  for (let index = 0; index < 90; index += 1) {
    const u = (index * 0.61803398875) % 1;
    particles.push(
      (u - 0.5) * 16,
      Math.sin(u * Math.PI * 8) * 1.7 + Math.sin(index * 2.1) * 0.22,
      Math.cos(u * Math.PI * 4) * 0.7 + Math.cos(index * 1.7) * 0.45,
    );
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute("position", new THREE.Float32BufferAttribute(particles, 3));
  scene.add(new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({ color: palette.cyan, size: 0.045, transparent: true, opacity: 0.74 }),
  ));
}

function makeWaveform(scene, data) {
  const positions = [];
  const duration = data.duration_seconds || data.points.at(-1)[0] || 1;
  for (const [time, amplitude] of data.points) {
    positions.push(((time / duration) - 0.5) * 16, amplitude * 4, 0);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: palette.teal }));
  line.computeLineDistances();
  scene.add(line);
  addAxisLine(scene, [-8, 0, 0], [8, 0, 0], palette.cyan);
  addAxisLine(scene, [-8, -4, 0], [-8, 4, 0], palette.amber);
}

function colorForDb(db) {
  const value = Math.max(0, Math.min(1, (db + 90) / 90));
  const color = new THREE.Color();
  color.setHSL(0.53 - 0.09 * value, 0.34 + 0.36 * value, 0.12 + 0.42 * value);
  return color;
}

function makeSpectrogram(scene, data) {
  const rows = data.magnitude_db.length;
  const columns = data.times.length;
  const frequencies = data.frequencies_hz;
  const maximumFrequency = frequencies.at(-1) || 1;
  const geometry = new THREE.BufferGeometry();
  const positions = [];
  const colors = [];
  const indices = [];
  const maximumTime = data.times.at(-1) || 1;
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const db = data.magnitude_db[row][column];
      const x = ((data.times[column] / maximumTime) - 0.5) * 14;
      const displayedDb = Math.max(-90, Math.min(0, db));
      const y = (frequencies[row] / maximumFrequency) * 10 - 5;
      const z = ((displayedDb + 90) / 90) * 4 - 2;
      positions.push(x, y, z);
      const color = colorForDb(displayedDb);
      colors.push(color.r, color.g, color.b);
    }
  }
  for (let row = 0; row < rows - 1; row += 1) {
    for (let column = 0; column < columns - 1; column += 1) {
      const a = row * columns + column;
      const b = a + columns;
      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }
  geometry.setIndex(indices);
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  const surface = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
      metalness: 0.08,
      roughness: 0.48,
    }),
  );
  scene.add(surface);
  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(geometry),
    new THREE.LineBasicMaterial({ color: 0x9bead8, transparent: true, opacity: 0.13 }),
  );
  scene.add(wire);
  addAxisLine(scene, [-7, -5, -2], [7, -5, -2], palette.cyan);
  addAxisLine(scene, [-7, -5, -2], [-7, 5, -2], palette.amber);
  addAxisLine(scene, [-7, -5, -2], [-7, -5, 2], palette.teal);
}

function disposeTree(scene) {
  scene.traverse((object) => {
    object.geometry?.dispose();
    if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
    else object.material?.dispose();
  });
}

export function mount(root, data) {
  let canvas = root.querySelector("canvas");
  const resetButton = root.querySelector("[data-reset-view]");
  const toolbar = root.querySelector(".toolbar");
  let fallbackObserver = null;
  const fallbackData = finiteData(data) ? data : { mode: "invalid" };
  const fallback = (note) => {
    if (resetButton) resetButton.hidden = true;
    if (toolbar) toolbar.hidden = true;
    canvas = drawFallback(canvas, fallbackData, note);
    if (canvas && !fallbackObserver) {
      fallbackObserver = new ResizeObserver(() => {
        canvas = drawFallback(canvas, fallbackData, note);
      });
      fallbackObserver.observe(root);
    }
    return () => fallbackObserver?.disconnect();
  };
  if (!finiteData(data)) {
    return fallback("Invalid visualization values; showing a safe fallback.");
  }
  let context;
  try {
    context = canvas.getContext("webgl2", { alpha: true, antialias: true });
    if (!context) throw new Error("WebGL 2 is unavailable");
  } catch (_error) {
    return fallback("WebGL is unavailable; this local 2D view is shown instead.");
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, context, alpha: true, antialias: true });
  } catch (_error) {
    return fallback("WebGL could not start; this local 2D view is shown instead.");
  }
  canvas.dataset.renderMode = "webgl2";
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(palette.background);
  scene.fog = new THREE.Fog(palette.background, 25, 60);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  if (data.mode === "spectrogram") {
    camera.up.set(0, 0, 1);
    camera.position.set(0, -18, 13);
  } else {
    camera.position.set(0, 5, data.mode === "hero" ? 21 : 17);
  }
  scene.add(new THREE.HemisphereLight(0xbde8e0, 0x10222b, 2.0));
  const keyLight = new THREE.DirectionalLight(0x8ce8d7, 2.3);
  keyLight.position.set(-3, 8, 8);
  scene.add(keyLight);
  const grid = new THREE.GridHelper(20, 20, palette.grid, 0x17323a);
  if (data.mode === "spectrogram") {
    grid.position.set(0, 0, -2);
    grid.rotation.x = Math.PI / 2;
  } else {
    grid.position.y = -4.2;
  }
  scene.add(grid);
  if (data.mode === "hero") makeHero(scene);
  else if (data.mode === "waveform") makeWaveform(scene, data);
  else makeSpectrogram(scene, data);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.075;
  controls.minDistance = 8;
  controls.maxDistance = 34;
  controls.autoRotate = data.mode === "hero" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  controls.autoRotateSpeed = 0.3;
  controls.saveState();
  controls.listenToKeyEvents(window);
  const reset = () => controls.reset();
  resetButton?.addEventListener("click", reset);

  const notice = root.querySelector("#voxneuro-fallback-note");
  if (notice) notice.textContent = data.mode === "hero"
    ? "Decorative acoustic field · no patient recording"
    : "Interactive 3D view · drag to orbit · scroll to zoom";
  const axes = root.querySelector("[data-axis-labels]");
  if (axes) {
    axes.dataset.mode = data.mode;
    if (data.mode === "spectrogram") {
      const maxT = (data.times?.at(-1) || 0).toFixed(2);
      const maxF = (data.frequencies_hz?.at(-1) || 0).toFixed(0);
      axes.innerHTML = `<div><strong>Spectrogram 3D</strong> · Time: 0 – ${maxT}s · Freq: 0 – ${maxF} Hz</div>` +
        `<div style="display:inline-flex; align-items:center; gap:6px; margin-top:3px;">` +
        `<span style="font-size:10px; color:#A7B8B5;">-90 dB</span>` +
        `<span style="display:inline-block; width:70px; height:6px; border-radius:2px; background:linear-gradient(to right, #112d36, #2d7a72, #55d9c1); border: 1px solid rgba(85,217,193,0.3);"></span>` +
        `<span style="font-size:10px; color:#55D9C1; font-weight:600;">0 dB</span></div>`;
    } else if (data.mode === "waveform") {
      const dur = (data.duration_seconds || data.points?.at(-1)?.[0] || 0).toFixed(2);
      axes.innerHTML = `<div><strong>Waveform 3D</strong> · Time: 0 – ${dur}s · Amplitude: -1.0 to +1.0 FS</div>`;
    } else {
      axes.textContent = "Decorative acoustic field · no patient recording";
    }
  }
  let frame = 0;
  let renderedFrames = 0;
  let disposed = false;
  let dampingUntil = 0;
  const resize = () => {
    const bounds = root.getBoundingClientRect();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(Math.max(1, bounds.width), Math.max(1, bounds.height), false);
    camera.aspect = Math.max(0.1, bounds.width / Math.max(1, bounds.height));
    camera.updateProjectionMatrix();
    requestRender();
  };
  const observer = new ResizeObserver(resize);
  const draw = () => {
    frame = 0;
    if (disposed || document.hidden) return;
    controls.update();
    renderer.render(scene, camera);
    renderedFrames += 1;
    canvas.dataset.renderedFrames = String(renderedFrames);
    if (controls.autoRotate || performance.now() < dampingUntil) requestRender();
  };
  const handleControlsChange = () => {
    dampingUntil = performance.now() + 300;
    requestRender();
  };
  const requestRender = () => {
    if (!disposed && !document.hidden && frame === 0) frame = requestAnimationFrame(draw);
  };
  const contextLost = (event) => {
    event.preventDefault();
    disposed = true;
    if (frame !== 0) cancelAnimationFrame(frame);
    frame = 0;
    observer.disconnect();
    document.removeEventListener("visibilitychange", handleVisibility);
    controls.removeEventListener("change", handleControlsChange);
    controls.stopListenToKeyEvents();
    controls.dispose();
    disposeTree(scene);
    renderer.dispose();
    canvas.dataset.renderMode = "2d";
    fallback("WebGL was interrupted; this local 2D view is shown instead.");
  };
  renderer.domElement.addEventListener("webglcontextlost", contextLost, false);
  controls.addEventListener("change", handleControlsChange);
  const handleVisibility = () => {
    if (document.hidden) {
      if (frame !== 0) cancelAnimationFrame(frame);
      frame = 0;
    } else {
      requestRender();
    }
  };
  document.addEventListener("visibilitychange", handleVisibility);
  observer.observe(root);
  resize();
  requestRender();
  return () => {
    disposed = true;
    if (frame !== 0) cancelAnimationFrame(frame);
    frame = 0;
    observer.disconnect();
    document.removeEventListener("visibilitychange", handleVisibility);
    renderer.domElement.removeEventListener("webglcontextlost", contextLost);
    controls.removeEventListener("change", handleControlsChange);
    controls.stopListenToKeyEvents();
    resetButton?.removeEventListener("click", reset);
    controls.dispose();
    disposeTree(scene);
    renderer.dispose();
    fallbackObserver?.disconnect();
  };
}

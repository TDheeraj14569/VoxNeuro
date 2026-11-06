import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { chromium } from "playwright-core";

const baseUrl = process.env.VOXNEURO_URL ?? "http://127.0.0.1:8510";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
  ?? [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ].find(existsSync);
if (!executablePath) {
  throw new Error(
    "Set PLAYWRIGHT_CHROMIUM_EXECUTABLE to a local Chrome/Edge binary to run this smoke check.",
  );
}

function syntheticWav({ seconds = 3.4, frequency = 180, sampleRate = 16000 } = {}) {
  const sampleCount = Math.floor(seconds * sampleRate);
  const bytes = Buffer.alloc(44 + sampleCount * 2);
  bytes.write("RIFF", 0);
  bytes.writeUInt32LE(bytes.length - 8, 4);
  bytes.write("WAVE", 8);
  bytes.write("fmt ", 12);
  bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20);
  bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(sampleRate, 24);
  bytes.writeUInt32LE(sampleRate * 2, 28);
  bytes.writeUInt16LE(2, 32);
  bytes.writeUInt16LE(16, 34);
  bytes.writeUInt32LE(sampleCount * 2, 40);
  bytes.write("data", 36);
  for (let index = 0; index < sampleCount; index += 1) {
    const sample = Math.sin((2 * Math.PI * frequency * index) / sampleRate) * 0.18;
    bytes.writeInt16LE(Math.round(sample * 32767), 44 + index * 2);
  }
  return bytes;
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: [
    "--enable-webgl",
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader-webgl",
  ],
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByRole("heading", { name: "VoxNeuro", exact: true }).waitFor();

  const homeView = page.frameLocator("iframe").last();
  await homeView.locator("#viewer").waitFor({ timeout: 20000 });
  await homeView.getByRole("group", {
    name: "Interactive three-dimensional acoustic visualization",
  }).waitFor();
  await homeView.getByRole("img", {
    name: "Three-dimensional acoustic scene. Drag to orbit and scroll to zoom.",
  }).waitFor();
  const homeReset = homeView.getByRole("button", { name: "Reset 3D camera view" });
  await homeReset.focus();
  await homeReset.press("Enter");
  assert.equal(await page.locator("iframe").count(), 1, "Unexpected duplicate home viewers.");
  const homeMode = await homeView.locator("canvas").getAttribute("data-render-mode");
  assert.ok(["webgl2", "2d"].includes(homeMode), `Unexpected home render mode: ${homeMode}`);
  if (homeMode === "webgl2") {
    const homeCanvas = homeView.locator('canvas[data-rendered-frames]');
    await homeCanvas.waitFor();
    const iframeHandle = await page.locator("iframe").last().elementHandle();
    const homeFrame = await iframeHandle.contentFrame();
    const previousFrames = Number(await homeCanvas.getAttribute("data-rendered-frames"));
    await homeFrame.evaluate(async () => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
      document.dispatchEvent(new Event("visibilitychange"));
      await new Promise((resolve) => setTimeout(resolve, 80));
      Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await homeFrame.waitForFunction(
      (before) => Number(document.querySelector("canvas")?.dataset.renderedFrames) > before,
      previousFrames,
      { timeout: 3000 },
    );
  }
  assert.match(
    await homeView.locator("#voxneuro-fallback-note").innerText(),
    /Decorative acoustic field/,
  );
  if (process.env.VOXNEURO_HOME_SCREENSHOT_PATH) {
    await page.screenshot({
      path: process.env.VOXNEURO_HOME_SCREENSHOT_PATH,
      fullPage: true,
    });
  }

  await page.getByText("Voice assessment", { exact: true }).click();
  await page.getByText("Upload WAV", { exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-vowel.wav",
    mimeType: "audio/wav",
    buffer: syntheticWav(),
  });
  await page.getByRole("button", { name: "Analyze this recording" }).click();
  await page.getByText("Acoustic analysis complete.", { exact: true }).waitFor({ timeout: 90000 });

  await page.getByText("Signal analysis", { exact: true }).click();
  let signalView = page.frameLocator("iframe").last();
  await signalView.locator("[data-axis-labels]").waitFor({ timeout: 20000 });
  assert.equal(await page.locator("iframe").count(), 1, "Signal navigation duplicated the viewer.");
  assert.match(
    await signalView.locator("[data-axis-labels]").innerText(),
    /X Time \(s\).*Y Amplitude/,
  );
  const signalMode = await signalView.locator("canvas").getAttribute("data-render-mode");
  assert.ok(["webgl2", "2d"].includes(signalMode), `Unexpected signal render mode: ${signalMode}`);
  if (signalMode === "webgl2") {
    await signalView.locator('canvas[data-rendered-frames]').waitFor();
  }
  const detailStart = page.getByRole("slider", { name: "3D waveform detail start (s)" });
  const oldStart = await detailStart.inputValue();
  await detailStart.focus();
  await detailStart.press("ArrowRight");
  assert.notEqual(await detailStart.inputValue(), oldStart, "Waveform detail slider did not move.");
  await signalView.locator('[data-axis-labels][data-mode="waveform"]').waitFor({
    timeout: 20000,
  });
  const screenshotPath = process.env.VOXNEURO_SCREENSHOT_PATH;
  if (screenshotPath) {
    await signalView.locator("#viewer").screenshot({ path: screenshotPath });
  }

  await page.locator('[aria-label="3D visualization"]').scrollIntoViewIfNeeded();
  await page.getByRole("radio", { name: "Spectrogram" }).check({ force: true });
  signalView = page.frameLocator("iframe").last();
  await signalView.locator('[data-axis-labels][data-mode="spectrogram"]').waitFor({
    timeout: 20000,
  });
  assert.match(
    await signalView.locator("[data-axis-labels]").innerText(),
    /X Time \(s\).*Y Frequency \(Hz\).*Z Magnitude/,
  );
  await signalView.getByRole("button", { name: "Reset 3D camera view" }).click();
  await page.waitForTimeout(250);
  if (process.env.VOXNEURO_SPECTROGRAM_SCREENSHOT_PATH) {
    await signalView.locator("#viewer").screenshot({
      path: process.env.VOXNEURO_SPECTROGRAM_SCREENSHOT_PATH,
    });
  }
  assert.equal(pageErrors.length, 0, `Browser page errors: ${pageErrors.join("; ")}`);
  console.log(
    `PASS local browser flow: home=${homeMode}; waveform=${signalMode}; spectrogram/reset; no page errors`,
  );
} finally {
  await browser.close();
}

const fallbackBrowser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--disable-webgl"],
});
try {
  const fallbackPage = await fallbackBrowser.newPage({ viewport: { width: 1280, height: 900 } });
  await fallbackPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  const fallbackView = fallbackPage.frameLocator("iframe").last();
  await fallbackView.locator('canvas[data-render-mode="2d"]').waitFor({ timeout: 20000 });
  const fallbackFrameHandle = await fallbackPage.locator("iframe").last().elementHandle();
  const fallbackFrame = await fallbackFrameHandle.contentFrame();
  assert.equal(
    await fallbackFrame.locator("[data-reset-view]").evaluate((button) => button.hidden),
    true,
    "The inactive WebGL camera reset must be hidden in the 2D fallback.",
  );
  assert.match(
    await fallbackView.locator("#voxneuro-fallback-note").innerText(),
    /WebGL is unavailable.*2D view is shown instead/,
  );
  const fallbackCanvas = fallbackView.locator('canvas[data-render-mode="2d"]');
  const oldWidth = await fallbackCanvas.evaluate((canvas) => canvas.width);
  await fallbackPage.setViewportSize({ width: 820, height: 760 });
  await fallbackFrame.waitForFunction(
    (width) => document.querySelector('canvas[data-render-mode="2d"]')?.width !== width,
    oldWidth,
    { timeout: 3000 },
  );
  console.log("PASS WebGL-disabled fallback resizes and exposes no inactive camera control.");
} finally {
  await fallbackBrowser.close();
}

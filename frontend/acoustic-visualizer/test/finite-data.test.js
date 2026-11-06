import assert from "node:assert/strict";
import test from "node:test";
import { finiteData } from "../src/main.js";

test("finiteData accepts bounded waveform data", () => {
  assert.equal(finiteData({
    mode: "waveform",
    duration_seconds: 1,
    points: [[0, 0], [1, 0.4]],
  }), true);
});

test("finiteData rejects missing roots and malformed waveform points safely", () => {
  for (const value of [undefined, null, [], 42, { mode: "waveform", points: [null, 3] }]) {
    assert.doesNotThrow(() => finiteData(value));
    assert.equal(finiteData(value), false);
  }
  assert.equal(finiteData({
    mode: "waveform",
    duration_seconds: 1,
    points: [[0, 0], [Number.NaN, 0.2]],
  }), false);
});

test("finiteData validates spectrogram grid dimensions and numeric cells", () => {
  const valid = {
    mode: "spectrogram",
    times: [0, 1],
    frequencies_hz: [100, 200],
    magnitude_db: [[-30, -20], [-40, -10]],
  };
  assert.equal(finiteData(valid), true);
  assert.equal(finiteData({ ...valid, magnitude_db: [[-30], [-40, -10]] }), false);
  assert.equal(finiteData({ ...valid, magnitude_db: [[-30, Infinity], [-40, -10]] }), false);
});

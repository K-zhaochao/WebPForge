import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  inspectImage,
  validateDimensions,
  getSavings,
  formatBytes,
  outputFilename,
  MAX_FILE_BYTES,
} from "../site/image-codec.js";

const asset = (name) =>
  readFile(new URL(`../site/assets/${name}`, import.meta.url));

test("real JPEG and WebP photographs retain dimensions and accurate sizes", async () => {
  const samples = JSON.parse(await asset("samples.json"));
  for (const sample of samples) {
    const jpeg = await asset(`${sample.id}-original.jpg`);
    const webp = await asset(`${sample.id}.webp`);
    assert.deepEqual(inspectImage(jpeg), {
      mime: "image/jpeg",
      label: "JPG",
      width: 1600,
      height: 1200,
    });
    assert.deepEqual(inspectImage(webp), {
      mime: "image/webp",
      label: "WebP",
      width: 1600,
      height: 1200,
    });
    assert.equal(jpeg.length, sample.sourceBytes);
    assert.equal(webp.length, sample.outputBytes);
    assert.equal(getSavings(jpeg.length, webp.length).smaller, true);
  }
});

test("transparent PNG is accepted without treating alpha as animation", async () => {
  const png = await asset("favicon.png");
  assert.deepEqual(inspectImage(png), {
    mime: "image/png",
    label: "PNG",
    width: 48,
    height: 48,
  });
});

test("animation flags are rejected before a browser can flatten the file", async () => {
  const png = await asset("favicon.png");
  const animationChunk = Buffer.alloc(20);
  animationChunk.writeUInt32BE(8);
  animationChunk.write("acTL", 4);
  animationChunk.writeUInt32BE(2, 8);
  assert.throws(
    () =>
      inspectImage(
        Buffer.concat([png.subarray(0, 33), animationChunk, png.subarray(33)]),
      ),
    /动画/,
  );
  const webp = Buffer.alloc(30);
  webp.write("RIFF");
  webp.writeUInt32LE(22, 4);
  webp.write("WEBPVP8X", 8);
  webp.writeUInt32LE(10, 16);
  webp[20] = 2;
  assert.throws(() => inspectImage(webp), /动画/);
  assert.throws(() => inspectImage(Buffer.from("GIF89a0000000000")), /动画/);
});

test("malformed content and forged chunk lengths fail safely", async () => {
  assert.throws(
    () => inspectImage(Buffer.from("<svg>not a photograph</svg>")),
    /不完整|不受支持/,
  );
  assert.throws(() => inspectImage(Buffer.from([0xff, 0xd8])), /不完整/);
  const png = Buffer.from(await asset("favicon.png"));
  png.writeUInt32BE(0xffffffff, 33);
  assert.throws(() => inspectImage(png), /不完整/);
  const webp = Buffer.from(await asset("alpine.webp"));
  webp.writeUInt32LE(0xffffffff, 16);
  assert.throws(() => inspectImage(webp), /不完整/);
});

test("large dimensions are refused even in a small compressed PNG header", async () => {
  const png = Buffer.from(await asset("favicon.png"));
  png.writeUInt32BE(100000, 16);
  png.writeUInt32BE(100000, 20);
  assert.throws(() => inspectImage(png), /尺寸较大/);
  assert.throws(
    () => inspectImage(new Uint8Array(MAX_FILE_BYTES + 1)),
    /20 MB/,
  );
  assert.throws(() => validateDimensions(8193, 1), /尺寸较大/);
  assert.throws(() => validateDimensions(0, 0), /不完整/);
  assert.deepEqual(validateDimensions(4000, 4000), {
    width: 4000,
    height: 4000,
  });
});

test("size increase and tiny savings are displayed honestly", () => {
  assert.deepEqual(getSavings(1000, 390), {
    number: "−61",
    unit: "%",
    label: "体积减少，风景依旧。",
    smaller: true,
  });
  assert.equal(getSavings(1000, 1100).number, "+10");
  assert.equal(getSavings(1000, 1000).number, "0");
  assert.equal(getSavings(1000, 999).number, "<1");
  assert.equal(getSavings(1000, 1001).smaller, false);
  assert.equal(getSavings(100, 10000).unit, "×");
  assert.throws(() => getSavings(0, 1), RangeError);
  assert.equal(formatBytes(727968), "728 KB");
  assert.equal(formatBytes(18546837), "18.5 MB");
});

test("download filename preserves Chinese while removing path separators", () => {
  assert.equal(outputFilename("周末的山野.png"), "周末的山野.webp");
  assert.equal(outputFilename("../unsafe:name.jpg"), ".._unsafe_name.webp");
  assert.equal(outputFilename(".jpg"), "image.webp");
});

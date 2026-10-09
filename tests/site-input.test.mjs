import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { singleImageFile, hasFileDrag, bindImageIngress } from "../site/image-input.js";

class Target {
  constructor() { this.events = new Map(); }
  addEventListener(type, handler) {
    if (!this.events.has(type)) this.events.set(type, []);
    this.events.get(type).push(handler);
  }
  emit(type, data = {}) {
    const event = {defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...data};
    for (const handler of this.events.get(type) || []) handler(event);
    return event;
  }
}
function fixture() {
  const document = new Target();
  const target = new Target();
  const files = [], errors = [], drags = [];
  const binding = bindImageIngress({document, target, onFile: (file) => files.push(file), onError: (error) => errors.push(error), onDrag: (active) => drags.push(active)});
  return { document, target, files, errors, drags, binding };
}
const photo = {name: "我的图片.png", type: "image/png"};

test("picker/drop/paste accept a single file and do not silently discard batches", () => {
  assert.equal(singleImageFile([photo]), photo);
  assert.equal(singleImageFile([]), null);
  assert.equal(singleImageFile(null), null);
  assert.throws(() => singleImageFile([photo, photo]), /一次请选择一张图片/);
  const f = fixture();
  f.binding.accept([photo]);
  f.binding.accept([photo, photo]);
  assert.deepEqual(f.files, [photo]);
  assert.equal(f.errors.length, 1);
});

test("file dragging prevents navigation, selects the dropped file and clears highlights", () => {
  const f = fixture();
  const dataTransfer = {types: ["Files"], files: [photo]};
  assert.ok(f.document.emit("dragover", {dataTransfer}).defaultPrevented);
  f.target.emit("dragenter", {dataTransfer});
  f.target.emit("dragenter", {dataTransfer});
  f.target.emit("dragleave", {dataTransfer});
  assert.deepEqual(f.drags, [true, true]); // Still inside a child element.
  f.target.emit("dragover", {dataTransfer});
  assert.equal(dataTransfer.dropEffect, "copy");
  assert.ok(f.target.emit("drop", {dataTransfer}).defaultPrevented);
  assert.deepEqual(f.files, [photo]);
  assert.equal(f.drags.at(-1), false);
  assert.ok(f.document.emit("drop", {dataTransfer}).defaultPrevented);
});

test("text dragging is untouched and batches leave the previous result intact", () => {
  const f = fixture();
  assert.equal(hasFileDrag({types: ["text/plain"]}), false);
  assert.equal(hasFileDrag({items: [{kind: "file"}]}), true);
  assert.equal(f.document.emit("dragover", {dataTransfer: {types: ["text/plain"]}}).defaultPrevented, false);
  f.target.emit("drop", {dataTransfer: {types: ["Files"], files: [photo, photo]}});
  assert.equal(f.files.length, 0);
  assert.equal(f.errors.length, 1);
  assert.equal(f.drags.at(-1), false);
});

test("image paste works without touching text paste, editable fields or handled events", () => {
  const f = fixture();
  const item = {kind: "file", type: "image/png", getAsFile: () => photo};
  assert.ok(f.document.emit("paste", {clipboardData: {items: [item]}}).defaultPrevented);
  assert.deepEqual(f.files, [photo]);
  assert.equal(f.document.emit("paste", {clipboardData: {items: [{kind: "string", type: "text/plain"}]}}).defaultPrevented, false);
  f.document.emit("paste", {target: {closest: () => true}, clipboardData: {items: [item]}});
  f.document.emit("paste", {defaultPrevented: true, clipboardData: {items: [item]}});
  f.document.emit("paste", {clipboardData: {items: [{...item, getAsFile: () => null}]}});
  assert.equal(f.files.length, 1);
  f.document.emit("paste", {clipboardData: {items: [item, item]}});
  assert.equal(f.errors.length, 1);
});

test("the first screen is an explicit empty input, not an automatic sample result", async () => {
  const html = await readFile(new URL("../site/index.html", import.meta.url), "utf8");
  const app = await readFile(new URL("../site/app.js", import.meta.url), "utf8");
  assert.match(html, /id="upload-dropzone"/);
  assert.match(html, /id="conversion-lab" hidden/);
  assert.ok(html.indexOf('id="upload-button"') < html.indexOf('id="conversion-lab"'));
  assert.match(html, /选择图片，在线转换/);
  assert.doesNotMatch(app, /selectSample\("alpine"\)/);
  assert.match(app, /state\.source = state\.output = null/);
  assert.match(app, /if \(selection !== state\.selectionVersion\) return/);
});

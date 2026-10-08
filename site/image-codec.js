/** Input checks run before image decoding, so huge or animated files are never
 * silently flattened or handed to the browser's full-size canvas allocator. */
export const MAX_FILE_BYTES = 20_000_000;
export const MAX_PIXELS = 16_000_000;
export const MAX_EDGE = 8192;

export class ImageInputError extends Error {}

const invalid = () =>
  new ImageInputError(
    "这张图片的内容不完整或格式不受支持，请选择静态 JPG、PNG 或 WebP。",
  );
const animated = () =>
  new ImageInputError("这是一张动画图片。请使用桌面版转换，以保留所有动画帧。");

export function validateDimensions(width, height) {
  if (
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    width < 1 ||
    height < 1
  )
    throw invalid();
  if (width * height > MAX_PIXELS || Math.max(width, height) > MAX_EDGE) {
    throw new ImageInputError(
      "这张图片尺寸较大。在线体验限 1,600 万像素、单边 8,192 像素；请用桌面版处理原图。",
    );
  }
  return { width, height };
}

export function inspectImage(input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (bytes.byteLength > MAX_FILE_BYTES)
    throw new ImageInputError("图片超过 20 MB，请使用桌面版处理这个文件。");
  if (bytes.byteLength < 12) throw invalid();
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const ascii = (offset, count) =>
    String.fromCharCode(...bytes.subarray(offset, offset + count));
  const result = (mime, label, width, height) => ({
    mime,
    label,
    ...validateDimensions(width, height),
  });

  if (ascii(0, 3) === "GIF") throw animated();

  if (
    bytes[0] === 137 &&
    ascii(1, 3) === "PNG" &&
    view.getUint32(4) === 0x0d0a1a0a
  ) {
    if (
      bytes.length < 33 ||
      view.getUint32(8) !== 13 ||
      ascii(12, 4) !== "IHDR"
    )
      throw invalid();
    const dimensions = result(
      "image/png",
      "PNG",
      view.getUint32(16),
      view.getUint32(20),
    );
    let hasPixels = false;
    for (let offset = 8; offset + 12 <= bytes.length; ) {
      const length = view.getUint32(offset);
      if (length > bytes.length - offset - 12) throw invalid();
      const chunk = ascii(offset + 4, 4);
      if (chunk === "acTL") throw animated();
      if (chunk === "IDAT") hasPixels = true;
      if (chunk === "IEND") {
        if (!hasPixels) throw invalid();
        return dimensions;
      }
      offset += length + 12;
    }
    throw invalid();
  }

  if (ascii(0, 4) === "RIFF" && ascii(8, 4) === "WEBP") {
    const end = view.getUint32(4, true) + 8;
    if (end > bytes.length || end < 20) throw invalid();
    let dimensions;
    let hasPixels = false;
    const uint24 = (offset) =>
      bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);
    for (let offset = 12; offset + 8 <= end; ) {
      const chunk = ascii(offset, 4);
      const length = view.getUint32(offset + 4, true);
      const start = offset + 8;
      if (length > end - start) throw invalid();
      if (chunk === "ANIM" || chunk === "ANMF") throw animated();
      if (chunk === "VP8X") {
        if (length < 10) throw invalid();
        if (bytes[start] & 2) throw animated();
        dimensions = result(
          "image/webp",
          "WebP",
          uint24(start + 4) + 1,
          uint24(start + 7) + 1,
        );
      }
      if (chunk === "VP8 ") {
        if (length < 10 || ascii(start + 3, 3) !== "\x9d\x01\x2a")
          throw invalid();
        hasPixels = true;
        dimensions ??= result(
          "image/webp",
          "WebP",
          view.getUint16(start + 6, true) & 0x3fff,
          view.getUint16(start + 8, true) & 0x3fff,
        );
      }
      if (chunk === "VP8L") {
        if (length < 5 || bytes[start] !== 0x2f) throw invalid();
        hasPixels = true;
        const bits = view.getUint32(start + 1, true);
        dimensions ??= result(
          "image/webp",
          "WebP",
          (bits & 0x3fff) + 1,
          ((bits >>> 14) & 0x3fff) + 1,
        );
      }
      offset = start + length + (length % 2);
    }
    if (!dimensions || !hasPixels) throw invalid();
    return dimensions;
  }

  if (bytes[0] === 0xff && bytes[1] === 0xd8) {
    const frameMarkers = new Set([
      0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce,
      0xcf,
    ]);
    let offset = 2;
    while (offset + 3 < bytes.length) {
      if (bytes[offset] !== 0xff) throw invalid();
      while (offset < bytes.length && bytes[offset] === 0xff) offset++;
      const marker = bytes[offset++];
      if (marker === 0xda || marker === 0xd9) break;
      if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
      if (offset + 2 > bytes.length) throw invalid();
      const length = view.getUint16(offset);
      if (length < 2 || offset + length > bytes.length) throw invalid();
      if (frameMarkers.has(marker)) {
        if (length < 8) throw invalid();
        return result(
          "image/jpeg",
          "JPG",
          view.getUint16(offset + 5),
          view.getUint16(offset + 3),
        );
      }
      offset += length;
    }
  }
  throw invalid();
}

export function formatBytes(value) {
  if (value < 1000) return `${value} B`;
  if (value < 1_000_000) return `${Math.round(value / 1000)} KB`;
  return `${(value / 1_000_000).toFixed(1)} MB`;
}

export function getSavings(original, converted) {
  if (original <= 0 || converted <= 0)
    throw new RangeError("File sizes must be positive.");
  const percent = (1 - converted / original) * 100;
  const rounded = Math.round(Math.abs(percent));
  if (converted / original >= 10) {
    return {
      number: (converted / original).toFixed(1),
      unit: "×",
      label: "结果体积 / 原图体积",
      smaller: false,
    };
  }
  if (!rounded) {
    return {
      number: percent === 0 ? "0" : "<1",
      unit: "%",
      label:
        percent === 0
          ? "体积没有变化"
          : percent > 0
            ? "体积略微减少"
            : "体积略微增加",
      smaller: percent > 0,
    };
  }
  return {
    number: `${percent > 0 ? "−" : "+"}${rounded}`,
    unit: "%",
    label:
      percent > 0 ? "体积减少，风景依旧。" : "体积增加，可以试试降低画质。",
    smaller: percent > 0,
  };
}

export function outputFilename(name) {
  const stem =
    name
      .replace(/\.[^.]+$/, "")
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
      .replace(/[ .]+$/, "")
      .slice(0, 110) || "image";
  return `${stem}.webp`;
}

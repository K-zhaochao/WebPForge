import { ImageInputError } from "./image-codec.js";

/** One image at a time, regardless of whether it came from a picker, drop or paste. */
export function singleImageFile(files) {
  const list = Array.from(files || []);
  if (list.length > 1)
    throw new ImageInputError("一次请选择一张图片。批量转换请使用桌面版。");
  return list[0] || null;
}
export function hasFileDrag(transfer) {
  return Array.from(transfer?.types || []).includes("Files")
    || Array.from(transfer?.items || []).some((item) => item.kind === "file");
}

// Dependency-injected event targets let Node tests exercise real event handlers
// without injecting events or altering private state in a running browser.
export function bindImageIngress({ document, target, onFile, onError, onDrag }) {
  let depth = 0;
  const resetDrag = () => { depth = 0; onDrag(false); };
  const accept = (files) => {
    try {
      const file = singleImageFile(files);
      if (file) onFile(file);
    } catch (error) { onError(error); }
  };
  const protectNavigation = (event) => {
    if (hasFileDrag(event.dataTransfer)) event.preventDefault();
  };
  document.addEventListener("dragover", protectNavigation);
  document.addEventListener("drop", (event) => { protectNavigation(event); resetDrag(); });
  target.addEventListener("dragenter", (event) => {
    if (!hasFileDrag(event.dataTransfer)) return;
    event.preventDefault();
    depth++;
    onDrag(true);
  });
  target.addEventListener("dragover", (event) => {
    if (!hasFileDrag(event.dataTransfer)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  target.addEventListener("dragleave", (event) => {
    if (!hasFileDrag(event.dataTransfer)) return;
    depth = Math.max(0, depth - 1);
    if (!depth) onDrag(false);
  });
  target.addEventListener("drop", (event) => {
    if (!hasFileDrag(event.dataTransfer)) return;
    event.preventDefault();
    resetDrag();
    accept(event.dataTransfer.files);
  });
  document.addEventListener("paste", (event) => {
    if (event.defaultPrevented || event.target?.closest?.("input, textarea, [contenteditable]:not([contenteditable='false'])")) return;
    const files = Array.from(event.clipboardData?.items || [])
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile()).filter(Boolean);
    if (!files.length) return; // Ordinary text/URL paste remains untouched.
    event.preventDefault();
    accept(files);
  });
  return { accept, resetDrag };
}

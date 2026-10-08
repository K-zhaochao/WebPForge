import {
  ImageInputError,
  MAX_FILE_BYTES,
  inspectImage,
  validateDimensions,
  formatBytes,
  getSavings,
  outputFilename,
} from "./image-codec.js";

document.documentElement.classList.add("js");
const $ = (selector) => document.querySelector(selector);
const header = $(".site-header");
const menu = $(".menu-toggle");
const navigation = $("#primary-nav");
const setMenu = (open) => {
  header.classList.toggle("is-open", open);
  menu.setAttribute("aria-expanded", String(open));
  menu.setAttribute("aria-label", open ? "关闭导航菜单" : "打开导航菜单");
};
menu.addEventListener("click", () =>
  setMenu(menu.getAttribute("aria-expanded") !== "true"),
);
navigation.addEventListener("click", (event) => {
  if (event.target.closest("a")) setMenu(false);
});
document.addEventListener("click", (event) => {
  if (!header.contains(event.target)) setMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
    setMenu(false);
    menu.focus();
  }
});
const mobileQuery = matchMedia("(max-width: 700px)");
mobileQuery.addEventListener("change", () => setMenu(false));

const comparison = $("#comparison");
const compareRange = $("#compare-range");
const beforeImage = $("#before-image");
const afterImage = $("#after-image");
const qualityRange = $("#quality-range");
const qualityValue = $("#quality-value");
const status = $("#conversion-status");
const indicator = $("#result-indicator");
const download = $("#download-result");
const fileInput = $("#file-input");
const sampleButtons = [...document.querySelectorAll("[data-sample]")];

const state = {
  source: null,
  output: null,
  sourceVersion: 0,
  encodeVersion: 0,
  loading: false,
  timer: null,
  readController: null,
  encodeChain: Promise.resolve(),
  samples: new Map(),
};

function setStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle("is-error", error);
}

function syncDownload() {
  const ready =
    !state.loading &&
    state.output &&
    state.output.source === state.source &&
    state.output.quality === Number(qualityRange.value);
  download.setAttribute("aria-disabled", String(!ready));
  download.tabIndex = ready ? 0 : -1;
  if (ready) {
    download.href = state.output.url;
    download.download = outputFilename(state.source.file.name);
  } else {
    download.removeAttribute("href");
    download.removeAttribute("download");
  }
  return ready;
}

function showPending(message) {
  indicator.textContent = "转换中";
  $("#saving-number").textContent = "…";
  $("#saving-label").textContent = "正在计算真实体积";
  $("#converted-size").textContent = "—";
  setStatus(message);
  syncDownload();
}

function renderResult(output) {
  const savings = getSavings(output.source.file.size, output.blob.size);
  const number = $("#saving-number");
  number.textContent = savings.number;
  const unit = document.createElement("small");
  unit.textContent = savings.unit;
  number.append(unit);
  number.style.fontSize =
    savings.number.length > 5 ? "clamp(30px, 4vw, 52px)" : "";
  $("#saving-label").textContent = savings.label;
  $("#original-size").textContent = formatBytes(output.source.file.size);
  $("#converted-size").textContent = formatBytes(output.blob.size);
  $("#output-size-bar").style.width =
    `${Math.min(100, (output.blob.size / output.source.file.size) * 100)}%`;
  indicator.textContent = "真实转换";
  afterImage.src = output.url;
  afterImage.alt = `${output.source.label}，质量 ${output.quality} 的 WebP 转换结果`;
  setStatus(
    savings.smaller
      ? "转换完成。图片没有离开你的设备。"
      : "转换完成。如实保留结果，也如实显示大小。",
  );
  syncDownload();
}

function updateQualityLabel() {
  const quality = Number(qualityRange.value);
  qualityValue.value = String(quality);
  const position = ((quality - 1) / 99) * 100;
  qualityRange.style.background = `linear-gradient(to right, var(--lime) ${position}%, #515b45 ${position}%)`;
  $("#quality-help").textContent =
    quality === 100
      ? "100 仍为有损编码。需要无损？请用桌面版。"
      : quality < 50
        ? "体积更小了，也请留意纹理与边缘的细节。"
        : quality > 85
          ? "为细节多留一点空间，文件也会相应增大。"
          : quality === 80
            ? "80，适合大多数网页图片的起点。"
            : "让体积与细节，找到适合这张图片的平衡。";
}

function queueEncoding(immediate = false, recoveryNotice = null) {
  clearTimeout(state.timer);
  const version = ++state.encodeVersion;
  if (!state.source || state.loading) return;
  const source = state.source;
  const quality = Number(qualityRange.value);
  showPending("正在本地生成 WebP…");
  if (recoveryNotice) setStatus(recoveryNotice, true);
  state.timer = setTimeout(
    () => {
      // Serial encoding keeps memory bounded. Obsolete queued requests are skipped;
      // in-flight callbacks may finish, but cannot replace a newer image or result.
      state.encodeChain = state.encodeChain.then(async () => {
        if (version !== state.encodeVersion || state.loading) return;
        const canvas = document.createElement("canvas");
        let url;
        try {
          canvas.width = source.image.naturalWidth;
          canvas.height = source.image.naturalHeight;
          const context = canvas.getContext("2d");
          if (!context)
            throw new ImageInputError(
              "浏览器无法创建图片画布，请换用较新的浏览器，或下载桌面版。",
            );
          context.drawImage(source.image, 0, 0);
          const blob = await new Promise((resolve) =>
            canvas.toBlob(resolve, "image/webp", quality / 100),
          );
          if (version !== state.encodeVersion || source !== state.source)
            return;
          if (!blob || blob.type !== "image/webp") {
            throw new ImageInputError(
              "当前浏览器不支持 WebP 编码，请使用新版 Chrome、Edge、Firefox，或下载桌面版。",
            );
          }
          url = URL.createObjectURL(blob);
          const check = new Image();
          check.src = url;
          await check.decode();
          if (version !== state.encodeVersion || source !== state.source)
            return;
          const previous = state.output;
          state.output = { source, quality, blob, url };
          url = null;
          renderResult(state.output);
          if (recoveryNotice) setStatus(recoveryNotice, true);
          if (previous) URL.revokeObjectURL(previous.url);
        } catch (error) {
          if (version !== state.encodeVersion) return;
          indicator.textContent = "未完成";
          $("#saving-number").textContent = "—";
          $("#saving-label").textContent = "换个设置，或使用桌面版";
          setStatus(
            error instanceof ImageInputError
              ? error.message
              : "转换没有完成。请重选图片，或使用桌面版再试一次。",
            true,
          );
          // A previous output can remain visible, but must never be downloadable
          // as if it belonged to this failed request.
          if (state.output) URL.revokeObjectURL(state.output.url);
          state.output = null;
          afterImage.src = source.url;
          syncDownload();
        } finally {
          if (url) URL.revokeObjectURL(url);
          canvas.width = 0;
          canvas.height = 0;
        }
      });
    },
    immediate ? 0 : 160,
  );
}

async function loadSource(getFile, label, sampleId = null) {
  const version = ++state.sourceVersion;
  ++state.encodeVersion;
  clearTimeout(state.timer);
  state.readController?.abort();
  state.readController = new AbortController();
  state.loading = true;
  qualityRange.disabled = true;
  indicator.textContent = "读取中";
  setStatus("正在读取图片，准备本地转换…");
  syncDownload();
  let url;
  try {
    const file = await getFile(state.readController.signal);
    if (version !== state.sourceVersion) return;
    if (file.size > MAX_FILE_BYTES)
      throw new ImageInputError("图片超过 20 MB，请使用桌面版处理这个文件。");
    const metadata = inspectImage(await file.arrayBuffer());
    if (version !== state.sourceVersion) return;
    url = URL.createObjectURL(file);
    const image = new Image();
    image.src = url;
    await image.decode();
    if (version !== state.sourceVersion) return;
    validateDimensions(image.naturalWidth, image.naturalHeight);
    const previousSource = state.source;
    const previousOutput = state.output;
    state.source = {
      file,
      label: label || file.name,
      sampleId,
      image,
      url,
      metadata,
    };
    url = null;
    state.output = null;
    state.loading = false;
    beforeImage.src = state.source.url;
    afterImage.src = state.source.url;
    beforeImage.alt = `${state.source.label}原图`;
    afterImage.alt = `${state.source.label}，正在生成 WebP`;
    $("#before-format").textContent = metadata.label;
    $("#image-name").textContent = sampleId
      ? `${label} · ${file.name}`
      : file.name;
    $("#image-name").title = file.name;
    $("#image-dimensions").textContent =
      `${image.naturalWidth} × ${image.naturalHeight} PX`;
    $("#original-size").textContent = formatBytes(file.size);
    sampleButtons.forEach((button) => {
      const selected = button.dataset.sample === sampleId;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    qualityRange.disabled = false;
    if (previousSource) URL.revokeObjectURL(previousSource.url);
    if (previousOutput) URL.revokeObjectURL(previousOutput.url);
    queueEncoding(true);
  } catch (error) {
    if (version !== state.sourceVersion) return;
    state.loading = false;
    qualityRange.disabled = !state.source;
    const message =
      error instanceof ImageInputError
        ? error.message
        : "图片读取失败，请换一张图片，或重新选择示例。";
    if (state.output && state.output.quality === Number(qualityRange.value)) {
      renderResult(state.output);
    } else if (state.source) {
      // Invalid input must not strand a pending quality change. Resume the last
      // valid image with the current setting, keeping the input error visible.
      queueEncoding(true, message + " 已保留上一张图片继续处理。");
      return;
    } else {
      indicator.textContent = "未完成";
      $("#saving-number").textContent = "—";
      $("#saving-label").textContent = "选择一张静态图片，再试一次";
    }
    setStatus(message, true);
    syncDownload();
  } finally {
    if (url) URL.revokeObjectURL(url);
  }
}

function selectSample(id) {
  const sample = state.samples.get(id);
  if (!sample) {
    setStatus("示例暂时无法读取，你仍可以选择自己的图片。", true);
    return;
  }
  loadSource(
    async (signal) => {
      const response = await fetch(sample.source, { signal });
      if (!response.ok)
        throw new ImageInputError(
          "示例图片暂时无法载入，请稍后重试，或换成你的图片。",
        );
      return new File([await response.blob()], `${sample.id}.jpg`, {
        type: "image/jpeg",
      });
    },
    sample.label,
    id,
  );
}

compareRange.addEventListener("input", () => {
  const position = Number(compareRange.value);
  comparison.style.setProperty("--compare", `${position}%`);
  compareRange.setAttribute(
    "aria-valuetext",
    `原图占左侧 ${position}%，WebP 占右侧 ${100 - position}%`,
  );
});
qualityRange.addEventListener("input", () => {
  updateQualityLabel();
  queueEncoding();
});
sampleButtons.forEach((button) =>
  button.addEventListener("click", () => selectSample(button.dataset.sample)),
);
$("#upload-button").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileInput.value = "";
  if (file) loadSource(async () => file, file.name);
});
download.addEventListener("click", (event) => {
  if (!syncDownload()) event.preventDefault();
});

window.addEventListener("pagehide", (event) => {
  if (event.persisted) return;
  ++state.sourceVersion;
  ++state.encodeVersion;
  state.readController?.abort();
  clearTimeout(state.timer);
  if (state.source) URL.revokeObjectURL(state.source.url);
  if (state.output) URL.revokeObjectURL(state.output.url);
});

updateQualityLabel();
try {
  const response = await fetch("assets/samples.json");
  if (!response.ok) throw new Error("Sample manifest unavailable.");
  const samples = await response.json();
  state.samples = new Map(samples.map((sample) => [sample.id, sample]));
  // A user may already have chosen a local file while the manifest was loading.
  if (!state.sourceVersion) selectSample("alpine");
} catch {
  if (!state.sourceVersion) {
    indicator.textContent = "等待图片";
    setStatus("示例暂时无法载入。点击「换成我的图片」仍可在本地转换。", true);
  }
}

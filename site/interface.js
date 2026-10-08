import { english, normalize, translate } from "./messages.js";

const root = document.documentElement;
export const t = (message, values = {}) => Array.isArray(message)
  ? message.map((part) => t(part, values)).join(" ")
  : translate(message, root.lang, values);
const bindings = new Map();
const attributes = new Map();

// Only explicitly catalogued source text is localized. Filenames and uploaded
// image content are never treated as translation keys or markup.
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
const staticText = [];
while (walker.nextNode()) {
  const node = walker.currentNode;
  if (node.parentElement.closest("script, style, [data-language]")) continue;
  const key = normalize(node.data);
  if (Object.hasOwn(english, key) || /^v[\w.+-]+ 已发布$/.test(key) || key === "@@RELEASE_TAG@@ 已发布")
    staticText.push({ node, original: node.data, key, last: node.data });
}
const staticAttributes = [];
for (const element of document.querySelectorAll("[aria-label], [alt], [title], [aria-valuetext], meta[name='description'], meta[property='og:title'], meta[property='og:description']")) {
  for (const name of ["aria-label", "alt", "title", "aria-valuetext", "content"]) {
    const original = element.getAttribute(name);
    if (original && (Object.hasOwn(english, normalize(original)) || original.startsWith("下载 WebPForge ")))
      staticAttributes.push({ element, name, original, last: original });
  }
}
const originalTitle = document.title;

export function setText(element, message, values = {}) {
  bindings.set(element, { message, values });
  element.textContent = t(message, values);
}
export function setAttributeText(element, name, message, values = {}) {
  if (!attributes.has(element)) attributes.set(element, new Map());
  attributes.get(element).set(name, { message, values });
  element.setAttribute(name, t(message, values));
}
function renderLanguage() {
  for (const item of staticText) {
    // A converter may have replaced this node; never resurrect stale results.
    if (!item.node.isConnected || item.node.data !== item.last || bindings.has(item.node.parentElement)) continue;
    item.last = root.lang === "en"
      ? item.original.replace(/\S[\s\S]*\S|\S/, t(item.key)) : item.original;
    item.node.data = item.last;
  }
  for (const item of staticAttributes) {
    if (attributes.get(item.element)?.has(item.name) || item.element.getAttribute(item.name) !== item.last) continue;
    item.last = t(item.original);
    item.element.setAttribute(item.name, item.last);
  }
  for (const [element, { message, values }] of bindings) element.textContent = t(message, values);
  for (const [element, names] of attributes)
    for (const [name, { message, values }] of names) element.setAttribute(name, t(message, values));
  document.title = t(originalTitle);
  document.querySelector('meta[property="og:locale"]')?.setAttribute("content", root.lang === "en" ? "en_US" : "zh_CN");
  for (const button of document.querySelectorAll("[data-language]"))
    button.setAttribute("aria-pressed", String(button.dataset.language === root.lang));
  syncThemeButton();
}
function persist(key, value) {
  try { localStorage.setItem(key, value); } catch { /* Preferences remain active for this session. */ }
}
for (const button of document.querySelectorAll("[data-language]")) {
  button.addEventListener("click", () => {
    if (root.lang === button.dataset.language) return;
    root.lang = button.dataset.language;
    persist("webpforge-language", root.lang);
    renderLanguage();
    window.dispatchEvent(new Event("languagechange"));
  });
}

const themeButton = document.querySelector(".theme-toggle");
function syncThemeButton() {
  const dark = root.dataset.theme === "dark";
  themeButton.setAttribute("aria-pressed", String(dark));
  themeButton.setAttribute("aria-label", t(dark ? "切换到浅色主题" : "切换到暗色主题"));
  themeButton.title = themeButton.getAttribute("aria-label");
}
function setTheme(theme) {
  root.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === "dark" ? "#171a17" : "#f5f5ef";
  syncThemeButton();
}
let explicitTheme = false;
try { explicitTheme = ["light", "dark"].includes(localStorage.getItem("webpforge-theme")); } catch { /* session only */ }
themeButton.addEventListener("click", () => {
  explicitTheme = true;
  setTheme(root.dataset.theme === "dark" ? "light" : "dark");
  persist("webpforge-theme", root.dataset.theme);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
  if (!explicitTheme) setTheme(event.matches ? "dark" : "light");
});
window.addEventListener("storage", (event) => {
  if (event.key === "webpforge-language") {
    root.lang = event.newValue === "en" ? "en" : "zh-CN";
    renderLanguage();
    window.dispatchEvent(new Event("languagechange"));
  }
  if (event.key === "webpforge-theme") {
    explicitTheme = ["light", "dark"].includes(event.newValue);
    setTheme(explicitTheme ? event.newValue : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
});
renderLanguage();

// Navigation order follows the page and the current section is visible on both
// desktop and mobile. Scrolling is throttled to one measurement per frame.
const links = [...document.querySelectorAll("#primary-nav a[href^='#']")];
const sections = links.map((link) => document.querySelector(link.getAttribute("href")));
let frame = 0;
function updateNavigation() {
  frame = 0;
  const threshold = document.querySelector(".site-header").offsetHeight + 160;
  let active = -1;
  sections.forEach((section, index) => { if (section.getBoundingClientRect().top <= threshold) active = index; });
  links.forEach((link, index) => {
    if (index === active) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}
function scheduleNavigation() { if (!frame) frame = requestAnimationFrame(updateNavigation); }
window.addEventListener("scroll", scheduleNavigation, { passive: true });
window.addEventListener("resize", scheduleNavigation);
window.addEventListener("languagechange", scheduleNavigation);
scheduleNavigation();

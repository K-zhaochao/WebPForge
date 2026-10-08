/* Runs before CSS: a saved/system theme is applied without a light-mode flash.
 * Preferences are the only user data stored. Image bytes never enter storage. */
(() => {
  const root = document.documentElement;
  let theme;
  let language;
  try {
    theme = localStorage.getItem("webpforge-theme");
    language = localStorage.getItem("webpforge-language");
  } catch { /* Private/storage-restricted browsing still works. */ }
  root.dataset.theme = theme === "light" || theme === "dark"
    ? theme : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  root.lang = language === "en" ? "en" : "zh-CN";
  root.classList.add("js");
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    "content", root.dataset.theme === "dark" ? "#171a17" : "#f5f5ef",
  );
})();

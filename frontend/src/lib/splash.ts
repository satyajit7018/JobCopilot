/** Fades out the start-up screen that index.html shows while the app loads. Safe to call more than once. */
export function hideSplash() {
  const el = document.getElementById("splash");
  if (!el || el.classList.contains("splash-out")) return;
  el.classList.add("splash-out");
  window.setTimeout(() => el.remove(), 300);
}

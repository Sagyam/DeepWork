// System / Light / Dark, as on the landing site and the other apps. A view
// preference, so it stays in this window's localStorage and never reaches
// deepworkd. index.html applies it before first paint; this keeps it live.

export type ThemePref = "system" | "light" | "dark";

const KEY = "theme";
const dark = matchMedia("(prefers-color-scheme: dark)");

export function themePref(): ThemePref {
  const v = localStorage.getItem(KEY);
  return v === "light" || v === "dark" ? v : "system";
}

function apply(pref: ThemePref) {
  const root = document.documentElement;
  root.classList.toggle("dark", pref === "dark" || (pref === "system" && dark.matches));
  root.dataset.theme = pref;
}

export function setThemePref(pref: ThemePref) {
  if (pref === "system") localStorage.removeItem(KEY);
  else localStorage.setItem(KEY, pref);
  apply(pref);
}

// Follow the desktop when it switches while the window is open.
dark.addEventListener("change", () => apply(themePref()));
apply(themePref());

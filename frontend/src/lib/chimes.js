/** Local office chimes — WAV files shipped with the app, never fetched from the internet. */
const CACHE = {};

export const CHIMES = ["login", "success", "error", "warning", "logout", "notify", "open"];

export function playChime(name) {
  if (typeof window === "undefined") return;
  try {
    if (window.localStorage?.getSoundMuted?.() || localStorage.getItem("ovc_mute_sounds") === "1") return;
    const key = CHIMES.includes(name) ? name : "notify";
    if (!CACHE[key]) {
      CACHE[key] = new Audio(`/sounds/${key}.wav`);
      CACHE[key].preload = "auto";
      CACHE[key].volume = 0.55;
    }
    const a = CACHE[key].cloneNode();
    a.volume = CACHE[key].volume;
    const p = a.play();
    if (p && p.catch) p.catch(() => {});
  } catch {
    /* autoplay policies or missing file must never break the office file */
  }
}

export function installToastChimes(toast) {
  if (!toast || toast.__ovcChimes) return toast;
  const wrap = (fn, chime) => (msg, opts) => {
    if (!opts?.silent) playChime(chime);
    return fn(msg, opts);
  };
  toast.success = wrap(toast.success.bind(toast), "success");
  toast.error = wrap(toast.error.bind(toast), "error");
  toast.warning = wrap(toast.warning.bind(toast), "warning");
  toast.info = wrap(toast.info.bind(toast), "notify");
  toast.__ovcChimes = true;
  return toast;
}

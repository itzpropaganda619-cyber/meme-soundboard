// Single-sound deep link page: try to autoplay immediately; fall back to a full-screen "tap anywhere" layer.
(() => {
  const S = window.SOUND;
  const tap = document.getElementById("tap");
  const big = document.getElementById("big");
  try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) {}

  // HTMLAudioElement for the autoplay attempt (browsers that allow autoplay / have engagement will just play)
  const audio = new Audio(S.file);
  audio.preload = "auto";
  audio.setAttribute("playsinline", "");

  // Web Audio for low-latency replays once unlocked by a gesture
  const AC = window.AudioContext || window.webkitAudioContext;
  let ctx = null, buffer = null, current = null;
  const bufP = fetch(S.file).then((r) => r.arrayBuffer());

  async function ensureCtx() {
    if (!ctx) ctx = new AC({ latencyHint: "interactive" });
    if (ctx.state !== "running") { try { await ctx.resume(); } catch (e) {} }
    if (!buffer) { const ab = (await bufP).slice(0); buffer = await new Promise((ok, err) => ctx.decodeAudioData(ab, ok, err)); }
  }

  function playFromGesture() {
    // must start something synchronously inside the gesture on iOS
    audio.currentTime = 0;
    const p = audio.play();
    if (p && p.catch) p.catch(() => {});
    ensureCtx(); // warm Web Audio for faster replays
  }

  function playAgain() {
    if (ctx && buffer && ctx.state === "running") {
      audio.pause();
      if (current) { try { current.stop(); } catch (e) {} }
      current = ctx.createBufferSource(); current.buffer = buffer; current.connect(ctx.destination); current.start(0);
    } else playFromGesture();
  }

  function showTap() { tap.classList.remove("hidden"); }
  function hideTap() { tap.classList.add("hidden"); }

  async function tryAutoplay() {
    audio.currentTime = 0;
    try { await audio.play(); hideTap(); }
    catch (e) { showTap(); }  // NotAllowedError on iOS Safari without a gesture
  }

  // click (= touchend on iOS) is the event iOS reliably treats as a user gesture for audio
  tap.addEventListener("click", (e) => { e.preventDefault(); playFromGesture(); hideTap(); });
  big.addEventListener("pointerdown", () => { big.classList.add("down"); if (ctx && buffer && ctx.state === "running") { big._done = true; playAgain(); } });
  big.addEventListener("click", () => { if (big._done) { big._done = false; return; } playAgain(); });
  ["pointerup", "pointercancel", "pointerleave"].forEach((ev) => big.addEventListener(ev, () => big.classList.remove("down")));

  tryAutoplay();
  // Home Screen web apps are often resumed rather than relaunched: try again whenever it comes back to the foreground
  let hiddenAt = 0;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { hiddenAt = Date.now(); return; }
    if (Date.now() - hiddenAt > 800) tryAutoplay();
  });
  window.addEventListener("pageshow", (e) => { if (e.persisted) tryAutoplay(); });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("../../sw.js", { scope: "../../" }).catch(() => {});
})();

// Meme Soundboard — Web Audio engine with decoded, preloaded buffers for instant playback.
(() => {
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC({ latencyHint: "interactive" });
  // iOS 17+: play through the silent switch like a media app (otherwise Web Audio follows the ringer switch)
  try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) {}
  const master = ctx.createGain(); master.connect(ctx.destination);
  const buffers = new Map();      // slug -> AudioBuffer
  const playing = new Map();      // slug -> Set<AudioBufferSourceNode>
  let overlap = localStorage.getItem("overlap") !== "off"; // on: different sounds can stack; off: one at a time
  let sounds = [];

  const grid = document.getElementById("grid");
  const modeBtn = document.getElementById("mode");
  const renderMode = () => (modeBtn.textContent = "Overlap: " + (overlap ? "on" : "off"));
  renderMode();
  modeBtn.onclick = () => { overlap = !overlap; localStorage.setItem("overlap", overlap ? "on" : "off"); renderMode(); };
  document.getElementById("stop").onclick = () => stopAll();

  // Unlock audio on the very first touch anywhere (required by iOS)
  const unlock = () => {
    if (ctx.state !== "running") ctx.resume();
    const b = ctx.createBuffer(1, 1, 22050), s = ctx.createBufferSource(); s.buffer = b; s.connect(master); s.start(0);
  };
  // iOS only grants audio permission on touchend/click (not touchstart), so keep trying until the context runs
  const unlockEvents = ["touchstart", "touchend", "pointerdown", "click", "keydown"];
  const tryUnlock = () => { unlock(); if (ctx.state === "running") unlockEvents.forEach((ev) => document.removeEventListener(ev, tryUnlock, true)); };
  unlockEvents.forEach((ev) => document.addEventListener(ev, tryUnlock, { capture: true, passive: true }));
  document.addEventListener("visibilitychange", () => { if (!document.hidden && ctx.state !== "running") ctx.resume().catch(() => {}); });

  function stopSlug(slug) {
    const set = playing.get(slug); if (!set) return;
    set.forEach((src) => { try { src.stop(); } catch (e) {} });
    set.clear();
    const el = grid.querySelector(`[data-slug="${slug}"]`); if (el) el.classList.remove("playing");
  }
  function stopAll() { [...playing.keys()].forEach(stopSlug); }

  function play(slug) {
    if (ctx.state !== "running") ctx.resume();
    const buf = buffers.get(slug);
    if (!buf) return;
    // Same button again = restart it (no pile-up of the same clip). Overlap off = stop everything else too.
    if (overlap) stopSlug(slug); else stopAll();
    const src = ctx.createBufferSource();
    src.buffer = buf; src.connect(master); src.start(0);
    if (!playing.has(slug)) playing.set(slug, new Set());
    playing.get(slug).add(src);
    const el = grid.querySelector(`[data-slug="${slug}"]`);
    if (el) { el.classList.remove("playing"); void el.offsetWidth; el.style.setProperty("--d", buf.duration + "s"); el.classList.add("playing"); }
    src.onended = () => { const s = playing.get(slug); if (s) { s.delete(src); if (!s.size && el) el.classList.remove("playing"); } };
    if (navigator.vibrate) navigator.vibrate(8);
  }

  function linkFor(slug) { return new URL(`s/${slug}/`, location.href).href; }

  // long-press -> share sheet with the per-sound link
  const sheet = document.getElementById("sheet");
  function openSheet(snd) {
    document.getElementById("sheetTitle").textContent = `${snd.emoji} ${snd.name}`;
    const url = linkFor(snd.slug);
    document.getElementById("sheetOpen").href = url;
    document.getElementById("sheetCopy").onclick = async () => {
      try { if (navigator.share) await navigator.share({ title: snd.name, url }); else { await navigator.clipboard.writeText(url); document.getElementById("sheetCopy").textContent = "Copied!"; } } catch (e) {}
    };
    document.getElementById("sheetCopy").textContent = navigator.share ? "Share link…" : "Copy link";
    sheet.classList.remove("hidden");
  }
  document.getElementById("sheetClose").onclick = () => sheet.classList.add("hidden");
  sheet.onclick = (e) => { if (e.target === sheet) sheet.classList.add("hidden"); };

  function render(filter = "") {
    grid.innerHTML = "";
    const f = filter.trim().toLowerCase();
    for (const snd of sounds) {
      if (f && !(snd.name.toLowerCase().includes(f) || snd.slug.includes(f))) continue;
      const b = document.createElement("button");
      b.className = "pad" + (buffers.has(snd.slug) ? "" : " loading");
      b.dataset.slug = snd.slug;
      b.style.setProperty("--c", snd.color);
      b.innerHTML = `<span class="emoji"></span><span class="label"></span>`;
      b.querySelector(".emoji").textContent = snd.emoji;
      b.querySelector(".label").textContent = snd.name;
      let pressTimer = null, longPressed = false;
      b.addEventListener("pointerdown", (e) => {
        longPressed = false; b.classList.add("down");
        if (ctx.state === "running") play(snd.slug); // fire on touch-down for minimum latency
        else b._pending = true; // first-ever tap on iOS: audio unlocks on touchend, play then
        pressTimer = setTimeout(() => { longPressed = true; b.classList.remove("down"); openSheet(snd); }, 600);
      });
      const up = () => { clearTimeout(pressTimer); b.classList.remove("down"); };
      b.addEventListener("pointerup", up); b.addEventListener("pointercancel", up); b.addEventListener("pointerleave", up);
      b.addEventListener("click", () => { if (b._pending && !longPressed) { b._pending = false; unlock(); play(snd.slug); } });
      b.addEventListener("contextmenu", (e) => { e.preventDefault(); });
      b.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); play(snd.slug); } });
      grid.appendChild(b);
    }
  }
  document.getElementById("q").addEventListener("input", (e) => render(e.target.value));

  async function load() {
    const res = await fetch("sounds.json", { cache: "no-cache" });
    sounds = await res.json();
    render();
    // preload + decode all buffers in parallel
    await Promise.all(sounds.map(async (snd) => {
      try {
        const ab = await (await fetch("sounds/" + snd.file)).arrayBuffer();
        const buf = await new Promise((ok, err) => ctx.decodeAudioData(ab, ok, err)); // callback form for older Safari
        buffers.set(snd.slug, buf);
        const el = grid.querySelector(`[data-slug="${snd.slug}"]`); if (el) el.classList.remove("loading");
      } catch (e) { console.warn("failed to load", snd.file, e); }
    }));
  }
  load();

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  window.__soundboard = { play, stopAll, buffers, ctx };
})();

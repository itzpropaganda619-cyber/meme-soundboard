#!/usr/bin/env python3
"""iOS Shortcuts for every sound (called by tools/build.py).

For each sound in public/sounds.json:
  * compile a tiny Shortcut with Cherri (https://cherrilang.org):
        Text(<mp3 as base64>) -> Base64 Decode -> Set Name "<slug>.mp3" -> Play Sound
    The audio is EMBEDDED, so the Shortcut works offline and never opens a screen.
  * sign it ("anyone" mode) via RoutineHub's free HubSign service (Cherri --hubsign).
    iOS 15+ refuses unsigned .shortcut files; native signing needs macOS, HubSign is the
    standard Linux route (no Apple ID involved; only the public sound is uploaded).
  * write public/shortcuts/<slug>/<Name>.shortcut  (file name = name shown after import)
  * render public/shortcuts/index.html (list + copy-URL buttons + build-it-yourself steps)

Signed files are cached (tools/.shortcut_sigs.json) and only rebuilt when the mp3/name/color
change. If signing fails (offline, HubSign down) the old signed file is kept, or the sound
just shows the manual steps. Set SKIP_SHORTCUT_SIGN=1 to skip signing entirely.
"""
import hashlib, html, json, os, platform, re, shutil, subprocess, sys, tempfile, urllib.request, zipfile, base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public"
OUT = PUB / "shortcuts"
SIGS = ROOT / "tools" / ".shortcut_sigs.json"
CHERRI_VER = "v2.3.0"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "soundboard"
RECIPE = "b64-setname-playsound-v1"   # bump to force rebuild of every shortcut

# Shortcut icon colours Cherri supports, with approximate RGB
COLORS = {"red": "#ef4444", "darkorange": "#ea580c", "orange": "#f59e0b", "yellow": "#eab308", "green": "#22c55e",
          "teal": "#14b8a6", "lightblue": "#38bdf8", "blue": "#3b82f6", "darkblue": "#1e3a8a", "violet": "#8b5cf6",
          "purple": "#a855f7", "pink": "#ec4899", "taupe": "#a8a29e", "gray": "#6b7280", "darkgray": "#374151"}

def _rgb(h): h = h.lstrip("#"); return [int(h[i:i+2], 16) for i in (0, 2, 4)]
def nearest_color(hexc):
    c = _rgb(hexc)
    return min(COLORS, key=lambda k: sum((a - b) ** 2 for a, b in zip(c, _rgb(COLORS[k]))))

def safe_filename(name):
    s = re.sub(r'[\\/:*?"<>|#%&{}$!`=@+]', "", name).strip().strip(".")
    return s or "Sound"

def cherri_bin():
    found = shutil.which("cherri")
    if found: return found
    exe = CACHE / f"cherri-{CHERRI_VER}"
    if exe.exists(): return str(exe)
    arch = "arm64" if platform.machine() in ("aarch64", "arm64") else "x86_64"
    osn = "darwin" if sys.platform == "darwin" else "linux"
    url = f"https://github.com/electrikmilk/cherri/releases/download/{CHERRI_VER}/cherri_{osn}-{arch}.zip"
    CACHE.mkdir(parents=True, exist_ok=True)
    zp = CACHE / "cherri.zip"
    print("downloading", url, file=sys.stderr)
    urllib.request.urlretrieve(url, zp)
    with zipfile.ZipFile(zp) as z:
        member = next(n for n in z.namelist() if n.endswith("cherri"))
        exe.write_bytes(z.read(member))
    exe.chmod(0o755); zp.unlink()
    return str(exe)

def compile_signed(snd, mp3: Path, dest: Path):
    b64 = base64.b64encode(mp3.read_bytes()).decode()
    src = (
        "#include 'actions/crypto'\n#include 'actions/documents'\n#include 'actions/media'\n"
        f"#define name {snd['slug']}\n#define color {nearest_color(snd['color'])}\n#define glyph speaker\n\n"
        f'const b64 = "{b64}"\n'
        "const audio = base64Decode(b64)\n"
        f'const named = setName(audio, "{snd["slug"]}.mp3")\n'
        "playSound(named)\n")
    exe = cherri_bin()
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "s.cherri"; f.write_text(src)
        out = Path(td) / "out.shortcut"
        for attempt in range(3):
            r = subprocess.run([exe, str(f), "--hubsign", "--share=anyone", f"--output={out}", "--no-ansi"],
                               cwd=td, capture_output=True, text=True, timeout=180)
            if out.exists() and out.read_bytes()[:4] == b"AEA1":
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out, dest)
                return True
            print(f"  sign attempt {attempt+1} failed for {snd['slug']}: {(r.stdout + r.stderr).strip()[-300:]}", file=sys.stderr)
    return False

def build_files(sounds):
    """Returns {slug: 'slug/Name.shortcut' or None}."""
    sigs = json.loads(SIGS.read_text()) if SIGS.exists() else {}
    skip = os.environ.get("SKIP_SHORTCUT_SIGN") == "1"
    result, keep = {}, set()
    for snd in sounds:
        slug = snd["slug"]; keep.add(slug)
        mp3 = PUB / "sounds" / snd["file"]
        fname = safe_filename(snd["name"]) + ".shortcut"
        rel = f"{slug}/{fname}"
        dest = OUT / rel
        sig = hashlib.sha1((RECIPE + "|" + rel + "|" + snd["color"]).encode() + mp3.read_bytes()).hexdigest()
        existing = [p for p in (OUT / slug).glob("*.shortcut")] if (OUT / slug).exists() else []
        if dest.exists() and sigs.get(slug) == sig:
            result[slug] = rel; continue
        if not skip:
            print(f"signing shortcut: {snd['name']}", file=sys.stderr)
            ok = False
            try: ok = compile_signed(snd, mp3, dest)
            except Exception as ex: print("  shortcut build error:", ex, file=sys.stderr)
            if ok:
                for p in existing:
                    if p != dest: p.unlink()
                sigs[slug] = sig; result[slug] = rel; continue
        # fall back to any previously signed file (stale but valid), else none
        result[slug] = f"{slug}/{existing[0].name}" if existing else None
    if OUT.exists():
        for d in OUT.iterdir():
            if d.is_dir() and d.name not in keep:
                shutil.rmtree(d); sigs.pop(d.name, None)
    SIGS.write_text(json.dumps(sigs, indent=1, sort_keys=True) + "\n")
    return result

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<script>if(!location.pathname.endsWith("/"))location.replace(location.pathname+"/"+location.search+location.hash);</script>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>📲 iPhone one-tap sounds · Soundboard</title>
<meta name="theme-color" content="#14081f">
<link rel="apple-touch-icon" href="../icons/app-180.png">
<link rel="icon" type="image/png" href="../icons/app-192.png">
<link rel="stylesheet" href="../style.css?v={ver}">
</head>
<body class="sc">
<header class="top">
  <h1>📲 One-tap icons</h1>
  <a class="chip" href="../">← Sounds</a>
</header>
<section class="card steps">
  <h2>Easiest way (about 20 seconds per sound)</h2>
  <ol>
    <li>Tap <b>Add</b> next to a sound → the Shortcuts app opens → tap <b>Add Shortcut</b>.<br>
      <small>If nothing opens, tap <b>⬇︎ File</b> instead → <b>Download</b> → Safari's ⬇︎ Downloads → tap the file → <b>Add Shortcut</b>.</small></li>
    <li>In Shortcuts, <b>long-press</b> the new tile → <b>Share</b> → <b>Add to Home Screen</b>.</li>
    <li>Optional: tap the small icon there → <b>Choose Photo</b> to use this sound's icon (tap <b>🖼 Icon</b> below → long-press → <b>Save to Photos</b> first). Rename if you like → <b>Add</b>.</li>
  </ol>
  <p class="note">Tap the new Home Screen icon → it plays instantly. No app screen opens, it works offline (the sound is built into the shortcut), and it plays even with the silent switch on (it uses media volume). iOS shows a small “running” bubble at the top for a moment.</p>
</section>
<input id="q" class="search" type="search" placeholder="Search sounds…" autocomplete="off">
<main id="list" class="sc-list">
{items}
</main>
<details class="card steps">
  <summary><b>Build one yourself instead</b> (no download needed)</summary>
  <ol>
    <li>Tap <b>Copy</b> next to a sound to copy its link.</li>
    <li>Open <b>Shortcuts</b> → <b>+</b> → search <b>Get Contents of URL</b> → tap it → tap the blue URL field → <b>Paste</b>.</li>
    <li>Search <b>Play Sound</b> → tap it (it plays the “Contents of URL” automatically).</li>
    <li>Tap the name at the top → <b>Rename</b> (e.g. “Vine Boom”) → <b>Done</b>.</li>
    <li>Same name menu → <b>Add to Home Screen</b> → set icon/name → <b>Add</b>.</li>
    <li>More sounds: long-press the shortcut → <b>Duplicate</b> → open the copy → paste a different link → rename → Add to Home Screen.</li>
  </ol>
  <p class="note">This version streams the sound, so it needs internet. For offline: download the .mp3 (long-press link → Download Linked File), then use the <b>File</b> action (pick the mp3) instead of Get Contents of URL.</p>
</details>
<p class="foot">Shortcut files are signed so iOS will import them; each one only contains its sound and a “Play Sound” step.</p>
<script>
(function(){{
  var base = new URL("../", location.href).href;
  document.querySelectorAll(".sc-item").forEach(function(el){{
    var mp3 = base + el.dataset.mp3, sc = el.dataset.sc;
    el.querySelector(".url").textContent = mp3;
    var add = el.querySelector(".add");
    if (add && sc) add.href = "shortcuts://import-shortcut?url=" + encodeURIComponent(new URL(sc, location.href).href) + "&name=" + encodeURIComponent(el.dataset.name);
    el.querySelector(".copy").onclick = function(){{
      var b = this; function ok(){{ b.textContent = "Copied ✓"; setTimeout(function(){{ b.textContent = "Copy"; }}, 1500); }}
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(mp3).then(ok, fallback); else fallback();
      function fallback(){{ var t = document.createElement("textarea"); t.value = mp3; document.body.appendChild(t); t.select(); try {{ document.execCommand("copy"); ok(); }} catch(e) {{}} t.remove(); }}
    }};
  }});
  var q = document.getElementById("q");
  q.oninput = function(){{ var v = q.value.trim().toLowerCase();
    document.querySelectorAll(".sc-item").forEach(function(el){{ el.hidden = v && el.dataset.name.toLowerCase().indexOf(v) < 0; }}); }};
  if (location.hash) {{ var t = document.getElementById(location.hash.slice(1)); if (t) {{ t.classList.add("hl"); t.scrollIntoView({{block:"center"}}); }} }}
}})();
</script>
</body>
</html>
"""

ITEM = """<div class="sc-item" id="{slug}" style="--c:{color}" data-name="{name}" data-mp3="sounds/{file}" data-sc="{sc}">
  <div class="sc-head"><span class="sc-emoji">{emoji}</span><span class="sc-name">{name}</span>{buttons}</div>
  <div class="sc-url"><code class="url">sounds/{file}</code><button class="copy chip">Copy</button></div>
</div>"""

def build_page(sounds, ver):
    files = build_files(sounds)
    OUT.mkdir(exist_ok=True)
    items = []
    for s in sounds:
        rel = files.get(s["slug"])
        q = urllib.request.quote
        if rel:
            href = q(rel)
            buttons = (f'<a class="chip add" href="{href}">＋ Add</a>'
                       f'<a class="chip ghost" href="{href}" download>⬇︎ File</a>')
        else:
            href = ""; buttons = ""
        buttons += f'<a class="chip ghost" href="../icons/{s["slug"]}-512.png" target="_blank">🖼 Icon</a>'
        items.append(ITEM.format(slug=s["slug"], color=s["color"], name=html.escape(s["name"]), emoji=s["emoji"],
                                 file=q(s["file"]), sc=href, buttons=f'<span class="sc-btns">{buttons}</span>'))
    (OUT / "index.html").write_text(PAGE.format(ver=ver, items="\n".join(items)))
    n = sum(1 for v in files.values() if v)
    print(f"shortcuts page: {len(sounds)} sounds, {n} signed .shortcut files")

if __name__ == "__main__":
    build_page(json.loads((PUB / "sounds.json").read_text()), "dev")

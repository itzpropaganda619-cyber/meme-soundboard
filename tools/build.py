#!/usr/bin/env python3
"""Regenerate everything derived from public/sounds.json:
- icons (app + per-sound PNGs)
- per-sound deep-link pages  public/s/<slug>/index.html + manifest
- service worker cache version
Run:  python3 tools/build.py
"""
import json, hashlib, html, os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public"
DATA = PUB / "sounds.json"
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

def hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)

def make_icon(emoji, color, size, out, rounded=False):
    """Square icon (iOS rounds corners itself) with vertical gradient + emoji."""
    base = hex2rgb(color)
    top, bot = shade(base, 1.15), shade(base, 0.75)
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)) + (255,))
    # emoji: NotoColorEmoji is a bitmap font, only renders at 109px; scale after
    try:
        f = ImageFont.truetype(EMOJI_FONT, 109)
        e = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(e).text((80, 80), emoji, font=f, embedded_color=True, anchor="mm")
        bbox = e.getbbox()
        if bbox:
            e = e.crop(bbox)
            target = int(size * 0.62)
            scale = target / max(e.size)
            e = e.resize((max(1, int(e.size[0] * scale)), max(1, int(e.size[1] * scale))), Image.LANCZOS)
            img.alpha_composite(e, ((size - e.size[0]) // 2, (size - e.size[1]) // 2))
    except Exception as ex:
        print("emoji render failed:", ex, file=sys.stderr)
    img.convert("RGB").save(out, "PNG", optimize=True)

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<script>if(!location.pathname.endsWith("/"))location.replace(location.pathname+"/"+location.search+location.hash);</script>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<title>{emoji} {name}</title>
<meta name="theme-color" content="{color}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{name}">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="../../icons/{slug}-180.png">
<link rel="icon" type="image/png" href="../../icons/{slug}-192.png">
<meta property="og:title" content="{emoji} {name}">
<meta property="og:image" content="../../icons/{slug}-512.png">
<link rel="stylesheet" href="../../style.css?v={ver}">
</head>
<body class="single" style="--c:{color}">
<main class="single-wrap">
  <button id="big" class="big" aria-label="Play {name}"><span class="emoji">{emoji}</span><span class="label">{name}</span></button>
  <p class="hint" id="hint">Tap to play again</p>
  <a class="back" href="../../">← all sounds</a>
</main>
<div id="tap" class="tap hidden" role="button" aria-label="Tap anywhere to play">
  <div><div class="tap-emoji">{emoji}</div><div class="tap-text">Tap anywhere</div><div class="tap-sub">to play “{name}”</div></div>
</div>
<script>window.SOUND = {sound_json};</script>
<script src="../../single.js?v={ver}"></script>
</body>
</html>
"""

def main():
    sounds = json.loads(DATA.read_text())
    (PUB / "icons").mkdir(exist_ok=True)
    # app icons
    for s in (180, 192, 512):
        out = PUB / "icons" / f"app-{s}.png"
        make_icon("🔊", "#7c3aed", s, out)
    # version hash = content of sounds.json + static files
    h = hashlib.sha1(DATA.read_bytes())
    for f in ("app.js", "single.js", "style.css", "index.html"):
        p = PUB / f
        if p.exists(): h.update(p.read_bytes())
    ver = h.hexdigest()[:10]
    keep = set()
    for snd in sounds:
        slug = snd["slug"]; keep.add(slug)
        for s in (180, 192, 512):
            out = PUB / "icons" / f"{slug}-{s}.png"
            sig = f"{snd['emoji']}|{snd['color']}"
            sigf = PUB / "icons" / f".{slug}.sig"
            if not out.exists() or not sigf.exists() or sigf.read_text() != sig:
                make_icon(snd["emoji"], snd["color"], s, out)
        (PUB / "icons" / f".{slug}.sig").write_text(f"{snd['emoji']}|{snd['color']}")
        d = PUB / "s" / slug
        d.mkdir(parents=True, exist_ok=True)
        page_sound = {"slug": slug, "name": snd["name"], "emoji": snd["emoji"], "file": "../../sounds/" + snd["file"]}
        (d / "index.html").write_text(PAGE.format(
            name=html.escape(snd["name"]), emoji=snd["emoji"], color=snd["color"], slug=slug, ver=ver,
            sound_json=json.dumps(page_sound, ensure_ascii=False).replace("</", "<\\/")))
        man = {
            "name": f"{snd['name']}",
            "short_name": snd["name"][:12],
            "id": f"./s/{slug}/",
            "start_url": "./",
            "scope": "./",
            "display": "standalone",
            "background_color": snd["color"],
            "theme_color": snd["color"],
            "icons": [
                {"src": f"../../icons/{slug}-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": f"../../icons/{slug}-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            ],
        }
        (d / "manifest.webmanifest").write_text(json.dumps(man, ensure_ascii=False, indent=1))
    # remove pages for deleted sounds
    sdir = PUB / "s"
    if sdir.exists():
        for d in sdir.iterdir():
            if d.is_dir() and d.name not in keep:
                for f in d.iterdir(): f.unlink()
                d.rmdir()
    # service worker with versioned cache + precache list
    precache = ["./", "index.html", "app.js", "single.js", "style.css", "sounds.json", "manifest.webmanifest",
                "icons/app-180.png", "icons/app-192.png", "icons/app-512.png"]
    precache += ["sounds/" + s["file"] for s in sounds]
    sw = (ROOT / "tools" / "sw.template.js").read_text()
    sw = sw.replace("__VERSION__", ver).replace("__PRECACHE__", json.dumps(precache, indent=1))
    (PUB / "sw.js").write_text(sw)
    (PUB / "version.txt").write_text(ver + "\n")
    print(f"built {len(sounds)} sounds, version {ver}")

if __name__ == "__main__":
    main()

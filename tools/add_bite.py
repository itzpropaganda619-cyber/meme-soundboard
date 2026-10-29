#!/usr/bin/env python3
"""Link -> sound bite.

  tools/add_bite.py URL [--name "Name"] [--start 0:05] [--end 0:07.5] [--emoji 😂] [--color "#ef4444"]
                        [--slug my-slug] [--max 15] [--no-deploy] [--replace]

URL can be YouTube, TikTok, X/Twitter, Instagram, Reddit, a myinstants.com page, or a direct audio/video file.
Steps: download (yt-dlp / curl) -> clip (start/end) -> trim leading silence -> 2-pass EBU R128 loudness
normalize (-14 LUFS, -1.5 dBTP) -> 128k mp3 in public/sounds/ -> update public/sounds.json -> tools/build.py
-> tools/deploy.sh (git commit + push + Render deploy).
"""
import argparse, json, os, random, re, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public"
DATA = PUB / "sounds.json"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6", "#6366f1", "#8b5cf6", "#d946ef", "#ec4899", "#f43f5e"]
AUDIO_EXT = re.compile(r"\.(mp3|m4a|aac|wav|ogg|oga|opus|flac|webm|mp4|mov)(\?|$)", re.I)

def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run(cmd, check=True, text=True, **kw)

def ensure_tools():
    os.environ["PATH"] = str(Path.home() / ".local/bin") + os.pathsep + os.environ["PATH"]
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg missing: sudo apt-get install -y ffmpeg")
    if not shutil.which("yt-dlp"):
        run([sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "-U", "yt-dlp"])

def ts(v):
    """'1:02.5' / '62.5' / '0:01:02' -> seconds (float)."""
    if v is None: return None
    parts = [float(p) for p in str(v).split(":")]
    s = 0.0
    for p in parts: s = s * 60 + p
    return s

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:40] or "bite"

def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)

def download(url, tmp):
    """Returns (path, title_guess)."""
    m = re.match(r"https?://(www\.)?myinstants\.com/", url)
    if m and "/media/sounds/" not in url:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        mp3 = re.search(r"/media/sounds/[^'\"]+\.mp3", page)
        if not mp3: sys.exit("no mp3 found on myinstants page")
        title = re.search(r"<h1[^>]*>([^<]+)</h1>", page)
        out = tmp / "src.mp3"; fetch("https://www.myinstants.com" + mp3.group(0), out)
        return out, (title.group(1).strip() if title else None)
    if Path(url).expanduser().is_file():  # local audio/video file
        src = Path(url).expanduser(); out = tmp / ("src" + src.suffix); shutil.copyfile(src, out)
        return out, src.stem.replace("_", " ").replace("-", " ")
    if AUDIO_EXT.search(url.split("#")[0]):
        out = tmp / ("src" + AUDIO_EXT.search(url).group(0).split("?")[0])
        try:
            fetch(url, out); return out, Path(url.split("?")[0]).stem.replace("_", " ").replace("-", " ")
        except Exception as e:
            print("direct fetch failed, trying yt-dlp:", e, file=sys.stderr)
    # yt-dlp handles YouTube, TikTok, X, Instagram, Reddit, and most other sites
    info = subprocess.run(["yt-dlp", "--no-playlist", "--print", "%(title)s", "--skip-download", url],
                          capture_output=True, text=True)
    title = info.stdout.strip().splitlines()[0] if info.returncode == 0 and info.stdout.strip() else None
    # TikTok's separate "audio" format is often the background track / a stub, so take a muxed video stream there
    fmt = "best[vcodec^=h264][acodec!=none]/best[acodec!=none]/best" if "tiktok.com" in url else "bestaudio/best"
    run(["yt-dlp", "--no-playlist", "-f", fmt, "-x", "--audio-format", "wav",
         "-o", str(tmp / "src.%(ext)s"), url])
    files = sorted(tmp.glob("src.*"))
    if not files: sys.exit("yt-dlp produced no file")
    return files[0], title

def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0

def process(src, out, start, end, maxlen, keep_silence=False):
    tmp_wav = out.with_suffix(".clip.wav")
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start is not None: cmd += ["-ss", str(start)]
    cmd += ["-i", str(src)]
    length = None
    if end is not None: length = end - (start or 0)
    if length is None or length > maxlen: length = maxlen
    cmd += ["-t", str(length), "-vn", "-ac", "2", "-ar", "44100"]
    filters = []
    if not keep_silence:
        # strip leading + trailing silence so the bite hits instantly on tap
        filters.append("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02")
        filters.append("areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse")
    if filters: cmd += ["-af", ",".join(filters)]
    run(cmd + [str(tmp_wav)])
    d = duration(tmp_wav)
    if d < 0.05: sys.exit("clip is empty after trimming — check --start/--end")
    fade = f"afade=t=in:d=0.005,afade=t=out:st={max(0, d - 0.03):.3f}:d=0.03"
    # pass 1: measure loudness
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(tmp_wav), "-af",
                           "apad=whole_dur=3,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    jm = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", meas, re.S)
    af = fade
    if jm:
        j = json.loads(jm.group(0))
        if j["input_i"] not in ("-inf", "inf") and float(j["input_i"]) > -70:
            af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                  f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,"
                  f"aresample=44100,alimiter=limit=0.84:level=false:attack=1:release=50,{fade}")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp_wav), "-af", af, "-t", f"{d:.3f}",
         "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "128k", "-map_metadata", "-1", str(out)])
    tmp_wav.unlink(missing_ok=True)
    return duration(out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--name"); ap.add_argument("--slug")
    ap.add_argument("--start", help="e.g. 12.5 or 0:12.5"); ap.add_argument("--end", help="e.g. 15 or 0:15")
    ap.add_argument("--emoji", default=None); ap.add_argument("--color", default=None)
    ap.add_argument("--max", type=float, default=15.0, help="max seconds (default 15)")
    ap.add_argument("--keep-silence", action="store_true", help="don't trim leading/trailing silence")
    ap.add_argument("--replace", action="store_true", help="overwrite an existing sound with the same slug")
    ap.add_argument("--no-deploy", action="store_true", help="only update local files")
    a = ap.parse_args()
    ensure_tools()
    sounds = json.loads(DATA.read_text()) if DATA.exists() else []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src, title = download(a.url, tmp)
        name = a.name or (title or "New bite")[:40]
        slug = slugify(a.slug or name)
        existing = next((s for s in sounds if s["slug"] == slug), None)
        if existing and not a.replace:
            i = 2
            while any(s["slug"] == f"{slug}-{i}" for s in sounds): i += 1
            slug = f"{slug}-{i}"; existing = None
        (PUB / "sounds").mkdir(parents=True, exist_ok=True)
        out = PUB / "sounds" / f"{slug}.mp3"
        dur = process(src, out, ts(a.start), ts(a.end), a.max, a.keep_silence)
    entry = {
        "slug": slug, "name": name,
        "emoji": a.emoji or (existing or {}).get("emoji") or random.choice("😂🔥💀😳🤯🎉👀😭🤡🗿📢🚨"),
        "color": a.color or (existing or {}).get("color") or random.choice(COLORS),
        "file": out.name, "duration": round(dur, 2), "source": a.url,
    }
    if existing: sounds[sounds.index(existing)] = entry
    else: sounds.append(entry)
    DATA.write_text(json.dumps(sounds, ensure_ascii=False, indent=1) + "\n")
    print(f"added {entry['emoji']} {name}  ({dur:.2f}s)  -> public/sounds/{out.name}", file=sys.stderr)
    run([sys.executable, str(ROOT / "tools" / "build.py")])
    if not a.no_deploy:
        run(["bash", str(ROOT / "tools" / "deploy.sh"), f"Add bite: {name}"])
    print(json.dumps({"slug": slug, "name": name, "duration": round(dur, 2), "path": f"/s/{slug}/"}))

if __name__ == "__main__":
    main()

# Meme Soundboard (PWA)

Mobile-first soundboard. Static site in `public/` (no build step needed on the host).

- `/` — grid of sound buttons (Web Audio, preloaded + decoded buffers)
- `/s/<slug>/` — single-sound page with its own title, icon and manifest → "Add to Home Screen" for a one-tap sound icon
- `tools/add_bite.py URL [--name ..] [--start ..] [--end ..] [--emoji ..]` — link → clip → normalize → add → redeploy
- `tools/build.py` — regenerate icons, per-sound pages, service worker
- `tools/starter_pack.sh` — rebuild the starter pack from myinstants.com

Sound clips are short excerpts of popular internet memes sourced from myinstants.com, for personal use.

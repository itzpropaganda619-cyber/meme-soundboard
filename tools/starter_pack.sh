#!/usr/bin/env bash
# Rebuilds the starter pack from myinstants.com (run once; uses add_bite.py with --no-deploy)
set -e
cd "$(dirname "$0")/.."
M=https://www.myinstants.com/media/sounds
add(){ python3 tools/add_bite.py --no-deploy --replace "$@"; }
add "$M/vine-boom.mp3"                     --name "Vine Boom"        --slug vine-boom        --emoji "💥" --color "#ef4444"
add "$M/bruh-sound-effect_WstdzdM.mp3"     --name "Bruh"             --slug bruh             --emoji "😐" --color "#64748b"
add "$M/airhorn.mp3"                       --name "Airhorn"          --slug airhorn          --emoji "📯" --color "#f97316"
add "$M/sadtrombone.swf.mp3"               --name "Sad Trombone"     --slug sad-trombone     --emoji "🎺" --color "#3b82f6"
add "$M/roblox-death-sound_1.mp3"          --name "Oof"              --slug oof              --emoji "💀" --color "#a855f7"
add "$M/emotional-damage-meme.mp3"         --name "Emotional Damage" --slug emotional-damage --emoji "💔" --color "#e11d48"
add "$M/oh-no-no-no-no-laugh.mp3"          --name "Oh No No No"      --slug oh-no            --emoji "😱" --color "#eab308" --max 8
add "$M/erro.mp3"                          --name "Windows Error"    --slug windows-error    --emoji "🪟" --color "#0ea5e9"
add "$M/among-us-role-reveal-sound.mp3"    --name "Among Us"         --slug among-us         --emoji "📮" --color "#dc2626"
add "$M/taco-bell-bong-sfx.mp3"            --name "Taco Bell Bong"   --slug taco-bell        --emoji "🔔" --color "#7c3aed"
add "$M/metal-pipe-clang.mp3"              --name "Metal Pipe"       --slug metal-pipe       --emoji "🔩" --color "#78716c"
add "$M/fbi-open-up_dwLhIFf.mp3"           --name "FBI Open Up"      --slug fbi-open-up      --emoji "🚔" --color "#1d4ed8"
add "$M/and-his-name-is-john-cena.mp3"     --name "John Cena"        --slug john-cena        --emoji "🎺" --color "#16a34a" --max 7
add "$M/anime-wow-sound-effect.mp3"        --name "Anime Wow"        --slug anime-wow        --emoji "🤩" --color "#ec4899"
add "$M/awkward-cricket-sound-effect.mp3"  --name "Crickets"         --slug crickets         --emoji "🦗" --color "#15803d" --keep-silence --max 6
add "$M/ba-dum-tss_zeVX10M.mp3"            --name "Ba Dum Tss"       --slug ba-dum-tss       --emoji "🥁" --color "#f59e0b"
add "$M/spongebob-fail.mp3"                --name "SpongeBob Fail"   --slug spongebob-fail   --emoji "🧽" --color "#facc15"

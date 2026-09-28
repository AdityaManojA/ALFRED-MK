---
type: "query"
date: "2026-09-28T18:39:47.896458+00:00"
question: "Fix Spotify playback, Audio Core now-playing display, inverted startup play button, and avoid opening the Spotify desktop app."
contributor: "graphify"
outcome: "useful"
source_nodes: ["SpotifyClient", "TronScoreBackgroundPlayer", "TacticalAudioPlayerWidget", "JarvisUI"]
---

# Q: Fix Spotify playback, Audio Core now-playing display, inverted startup play button, and avoid opening the Spotify desktop app.

## Answer

Expanded from graph vocabulary: [spotify, playback, audio, core, track, state, player, pause, resume, device, current, control]. Replaced optimistic local and Spotify state with verified QMediaPlayer and Web API state; TRON now starts paused with a play icon. Spotify playback is API-only and never launches a URI or sends global media-key fallbacks. It selects an available unrestricted Connect device, returns actionable HTTP and authorization errors, and updates the UI only after confirmed success. Added a non-blocking ten-second current-playback sync, thread-safe JarvisUI signals, source-aware two-line title and artist display, SPOTIFY LIVE header and badge, and six regression tests. Sanitized live diagnostics confirmed user OAuth and two controllable devices. Focused tests passed; full suite passed 98 of 99 with one unrelated screen-grounding failure.

## Outcome

- Signal: useful

## Source Nodes

- SpotifyClient
- TronScoreBackgroundPlayer
- TacticalAudioPlayerWidget
- JarvisUI
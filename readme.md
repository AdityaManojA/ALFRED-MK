#  ALFRED — MARK-IV (Wayne Protocol Edition)
### Autonomous Multimodal AI Desktop Assistant & Tactical Terminal
**Architect & Lead Creator:** **ADITYA MANOJ**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![AI Backend](https://img.shields.io/badge/AI-Gemini%203.1%20Flash%20Live%20%7C%20Local%20Ollama-8E75B2.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Local LLMs](https://img.shields.io/badge/Local%20LLM-Ollama%20%7C%20LM%20Studio%20%7C%20vLLM-orange.svg)](https://ollama.com)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20Software%20Renderer-41CD52.svg?logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![AES-256 Remote](https://img.shields.io/badge/Mobile-Quantum%20Dashboard%20(iOS%2FAndroid)-00f0ff.svg)](https://github.com/AdityaManojA/ALFRED-MK-IV)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

> **ALFRED MARK-IV** is an autonomous, real-time voice, vision, and system-control executive assistant built for complete digital sovereignty and tactical computing. Featuring native bidirectional audio streaming, real-time visual grounding, full desktop automation, high-performance long-term memory, and encrypted mobile remote telemetry.

---

##  1. What's New: Recent Enhancements, Bug Fixes & Stability Updates

* **Tactical Audio Core Voice Control**: Introduced dedicated `actions/audio_core.py` action tool and UI methods (`pause_audio_core`, `resume_audio_core`), allowing users to control the ambient TRON Legacy score directly (*"pause audio core"*, *"resume audio core"*, *"audio core volume to 25%"*) without conflicting with Spotify routing.
* **Audio Starvation & Microphone Breakup Fix**: Reconfigured `sd.RawOutputStream` in `main.py` with `blocksize=0` for hardware-native buffer sizing, implemented dynamic jitter pre-buffering on utterance starts, and added a 3-count debounce grace period on `is_speaking`. This eliminates PortAudio buffer starvation on Windows, crackling, and mic self-collision flip-flops.
* **News Reading Interruption Leak Elimination**: Implemented strict cancellation flags (`self._briefing_cancelled = True`) and active background task cancellation in `main.py`. Interrupting ALFRED during the morning briefing or background topic monitoring now instantly silences playback and permanently prevents residual news paragraphs from resuming minutes later.
* **Spotify Media Toggle Inversion & Playback Loops**: Replaced blind `VK_MEDIA_PLAY_PAUSE (0xB3)` toggle with explicit Windows `WM_APPCOMMAND` messages (`APPCOMMAND_MEDIA_PAUSE=47`, `APPCOMMAND_MEDIA_PLAY=46`), eliminating recursive play/pause loops during voice commands.
* **Spotify Acoustic Feedback Elimination**: Decoupled synchronous TTS `speak()` calls from `actions/spotify_control.py`, preventing the microphone from picking up self-speech and triggering secondary duplicate tool calls.
* **Windows Console Encoding Resilience**: Standardized logging in `actions/spotify_control.py` to prevent Windows `charmap` UnicodeEncodeErrors on legacy terminal code pages.
* **Windows Modern Audio Endpoint Compatibility**: Fixed volume control in `actions/computer_settings.py` to interface with modern `pycaw.EndpointVolume` scalar setters, resolving attribute errors and eliminating PyAutoGUI mouse failsafe triggers.
* **Path Guard Word Filtering**: Refined `core/path_guard.py` to prevent false-positive path resolution on plain single-word tool parameters (such as `"Save"` or `"File"`).
* **HUD Volume Popup Geometry**: Resolved `QPoint` namespace issue during volume popup positioning in `ui.py`.
* **Mobile Remote Uplink & Web Dashboard Repair**:
  * **Tuple Unpacking & Argument Serialization Bug**: Eliminated a severe unpacking defect in `MainWindow._open_remote` (`ui.py`) where `manual = result = result[0]` inadvertently reassigned the return tuple to the URL string, causing subsequent indices to extract single letters (`'t'`, `'t'`, `'p'`, `':'`) and corrupting the overlay's QR code, manual coordinates, desktop link, and key.
  * **Clickable Hyperlinks & One-Click Browser Launch**: Upgraded `RemoteKeyOverlay` with `Qt.TextInteractionFlag.LinksAccessibleByMouse` and rich HTML anchors (`setOpenExternalLinks(True)`). Added an **`↗ OPEN IN BROWSER`** button for instant one-click dashboard launching on the host machine.
  * **Protocol Schema Enforcement**: Updated `dashboard/server.py` (`get_manual_url`) to dynamically prepend `http://` or `https://` schemas, ensuring standard URI resolution across mobile browsers and QR scanners.
  * **Instant Camera Pairing via Auto-Login Tokens**: Configured `main.py` (`_make_remote_key`) to pass full `/auto-login?key={key}` paths to both local LAN and localhost links, allowing mobile optical sensors to immediately recognize the QR code as a web view link and pair seamlessly.
* **Audio Stutter, Driver Jitter & 30-Second Frame Drop Elimination**:
  * **COM & NVML Driver Handle Caching**: Prevented periodic 40–100ms thread hangs during metric polling by persisting `wmi.WMI` COM namespaces and `pynvml.nvmlInit()` GPU device handles across calls in `actions/system_monitor.py`.
  * **Qt UI Thread Offload**: Decoupled heavy OS process counting (`len(psutil.pids())`) and boot time queries from Qt's 500ms main timer thread, shifting them to the background `_SysMetrics` daemon in `ui.py` to keep GUI frame rates at a consistent 60 FPS.
  * **PortAudio Stream Jitter Cushion & High-Latency Buffering**: Configured PortAudio output stream with `latency="high"` and elevated utterance start pre-buffering cushion to 250ms in `main.py`, absorbing Windows thread scheduling delays and eliminating voice dropouts.
  * **Python Generational GC Throttling & Idle Maintenance**: Raised Python GC generation 0/1/2 collection thresholds to `(70000, 15, 15)` to avoid stop-the-world garbage collection pauses during active voice streaming or visual rendering, coupled with an idle-only background GC manager in `main.py`.
* **Persona Directives, Speech Debounce & Cognitive Trace**:
  * **Quintessential British Butler Persona**: Overhauled master system prompt directives in `core/prompt.txt` to fully embody Alfred Pennyworth — dignified servitude, razor-sharp dry British wit, impeccable deference to "Master Wayne", and crisp, succinct verbal delivery.
  * **STT Speech Debounce & Instant Interrupt Bypass**: Raised speech completion debounce threshold to `FINISH_MS = 900` in `core/local_stt.py` to prevent premature sentence truncation, while retaining instant interrupt capabilities on stop/wake keywords.
  * **Cognitive Trace (Real-Time Chain-of-Thought Streamer)**: Introduced an interactive `THINKING TRACE: ON/OFF` toggle button above the HUD chat in `ui.py`, paired with a dedicated thinking streaming listener in `main.py` to display internal reasoning steps from thinking-enabled models.
  * **Protocol Engine Confirmation Loop Prevention**: Fixed `actions/protocol_engine.py` to bypass confirmation gates on non-destructive workflow creation (`ask_confirmation=False`), resolving recursive protocol generation loops.

---

##  2. 100% Local & Air-Gapped Offline Execution: Switching from Gemini to Local API

**ALFRED is architected for dual-backend operation**: you can seamlessly toggle between Google's high-speed **Gemini 3.1 Flash Live API** (cloud multimodal WebSocket) and **100% local, air-gapped open-weight models** (Ollama, LM Studio, vLLM, Jan, LocalAI, or llama.cpp) without changing a single line of application code.

###  Gemini Live API vs. Local Offline API Comparison

| Feature | Gemini 3.1 Flash Live | Local Open-Weight API (Ollama / vLLM / LM Studio) |
|---|---|---|
| **Audio Latency** | Sub-second native bidirectional WebSocket streaming | Local STT/TTS pipeline or text-streaming |
| **Privacy & Security** | Encrypted TLS to Google Cloud | 100% offline, zero network egress, fully air-gapped |
| **Hardware Requirements** | Zero local compute (runs on any CPU) | 8GB–24GB+ VRAM/RAM depending on quantized model size |
| **API Token Cost** | Pay-per-token or free tier quotas | **$0.00 forever** (unlimited free local inference) |
| **Tool / Function Calling** | Native Gemini Automatic Function Calling (AFC) | Tool-calling supported via JSON mode or prompt schema |
| **Offline Operation** | Requires active Internet connection | **Operates entirely without internet connection** |

---

###  Detailed Step-by-Step Guide: How to Switch to a Local API

#### Step 1: Install & Set Up Your Preferred Local LLM Server

Choose any of the following recommended local model engines:

##### Option A: Ollama (Recommended — Simplest Setup)
1. Download and run the installer for Windows, macOS, or Linux from [ollama.com](https://ollama.com/).
2. Open PowerShell or Terminal and pull your model of choice:
   ```powershell
   # Recommended for 8GB VRAM / RAM (Fast & Accurate):
   ollama pull llama3.2:3b-instruct-q4_K_M
   # Or for 16GB VRAM / RAM (High reasoning capacity):
   ollama pull qwen2.5:7b-instruct
   # Or for deep programming & tool execution:
   ollama pull deepseek-coder-v2:16b
   ```
3. Start the Ollama daemon (runs automatically in background at `http://localhost:11434` or verify with `ollama list`).

##### Option B: LM Studio (Recommended for GUI Users)
1. Download [LM Studio](https://lmstudio.ai/) and launch it.
2. Search and download any quantized GGUF model with tool-calling capabilities (e.g., `Qwen2.5-7B-Instruct-GGUF` or `Llama-3.1-8B-Instruct-GGUF`).
3. Click the **Local Server** tab (double-arrow icon `<->` on the left sidebar).
4. Set the port to `1234` (default) and click **Start Server**.
5. Your local OpenAI-compatible endpoint is now live at `http://localhost:1234/v1`.

##### Option C: vLLM or llama.cpp (High-Throughput / Linux Servers)
Run with your OpenAI-compatible API flag:
```bash
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct --port 8000
```

---

#### Step 2: Configure ALFRED's Target Backend in `config/api_keys.json`

Open `config/api_keys.json` in the root folder of ALFRED. Set `llm_provider`, `llm_url`, and `llm_model`:

##### Configuration Template for Ollama:
```json
{
    "llm_provider": "ollama",
    "llm_url": "http://localhost:11434",
    "llm_model": "llama3.2",
    "assistant_name": "ALFRED",
    "user_name": "Master Wayne",
    "ui_color": "#e5a93b",
    "voice_name": "Charon",
    "wake_word_enabled": true,
    "push_to_talk_enabled": true
}
```

##### Configuration Template for LM Studio / vLLM (OpenAI-Compatible):
```json
{
    "llm_provider": "openai",
    "llm_url": "http://localhost:1234/v1",
    "llm_model": "qwen2.5-7b-instruct",
    "assistant_name": "ALFRED",
    "user_name": "Master Wayne",
    "ui_color": "#e5a93b",
    "voice_name": "Charon",
    "wake_word_enabled": true,
    "push_to_talk_enabled": true
}
```

##### Configuration Template for OpenRouter API (Frontier Multi-Model Gateway):
```json
{
    "llm_provider": "openrouter",
    "openrouter_api_key": "sk-or-v1-YOUR_OPENROUTER_KEY",
    "openrouter_model": "anthropic/claude-3.5-sonnet",
    "assistant_name": "ALFRED",
    "user_name": "Master Wayne",
    "ui_color": "#e5a93b",
    "voice_name": "Charon",
    "wake_word_enabled": true,
    "push_to_talk_enabled": true
}
```
* **Frontier Model Variety**: OpenRouter provides unified access to top frontier models including:
  * `anthropic/claude-3.5-sonnet` (Deep analytical reasoning and code execution)
  * `google/gemini-2.0-flash-001` (Sub-second response speed)
  * `meta-llama/llama-3.3-70b-instruct` (State-of-the-art open weights)
  * `deepseek/deepseek-r1` (Reinforcement learning chain-of-thought)
  * `openai/gpt-4o` (Multi-modal intelligence)
  * `openrouter/auto` (Dynamic intelligent routing)
* **First-Run Setup Integration**: You can also configure your OpenRouter API key and model directly in the GUI during the initial startup system overlay (`◈ SYSTEM INITIALISATION // OPERATOR & NEURAL CONFIG`).

---

#### Step 3: Launch ALFRED & Verify Connection

Start ALFRED in your terminal:
```powershell
python main.py
```
* **Connection Handshake**: `core/llm_client.py` will probe your local endpoint during startup:
  ```text
  [LLM] Connected to local Ollama server at http://localhost:11434 (model: llama3.2)
  [Actions] Action discovery complete: 23 active.
  ```
* **Offline Wake Word**: When offline, ALFRED automatically utilizes `openwakeword` on your local CPU for zero-cloud keyword activation.

---

#### Step 4: How to Switch Back to Gemini Live API Anytime

To return to Gemini Live, either:
1. Re-add your `"gemini_api_key"` in `config/api_keys.json`:
   ```json
   {
       "gemini_api_key": "AIzaSyYourActualKeyHere...",
       "llm_provider": "gemini"
   }
   ```
2. Or set the system environment variable:
   ```powershell
   $env:GEMINI_API_KEY="AIzaSyYourActualKeyHere..."
   ```
ALFRED will automatically prioritize the Gemini Live bidirectional WebSocket when a valid key is detected.

---

## 🎭 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action)

ALFRED is infused with the personality, dry British wit, and unwavering dignity of **Alfred Pennyworth**. Beyond standard operational tools, ALFRED features immersive conversational Easter eggs, witty banter, and rapid-fire tactical shortcuts:

### 🎩 Distinguished Butler & Persona Banter
* *"Good morning, Alfred."* → Delivers an executive morning greeting with situational weather and dignified butler formality (*"Good morning, Master Wayne. A pleasure to see you awake on this fine day."*).
* *"Alfred, how do you look today?"* → Inquires about his cybernetic holographic avatar (*"I find my holographic profile impeccably groomed today, sir, though I do wonder if a tie might suit the digital realm."*).
* *"Alfred, give me some advice."* → Shares grounded, dry British wisdom tailored to Master Wayne’s relentless work habits (*"Might I suggest, sir, that sleep is occasionally an acceptable substitute for caffeine?"*).
* *"Who is Batman?"* → Delivers a discreet, knowing butler response protecting your secret identity.
* *"Alfred, tell me a joke."* → Serves a razor-sharp, understated piece of dry British wit without breaking composure.
* *"Are you ready for the night shift, Alfred?"* → Engages night tactical readiness mode.

### 👁️ Tactical Vision & Screen Grounding
* *"Look at my screen and tell me why this code isn't compiling."* → Captures the active IDE window, analyzes the stack trace, and explains the bug succinctly.
* *"Look at my webcam, how do I look?"* → Takes a single situational webcam snapshot and delivers a candid opinion on your presentation.
* *"Click that green button on the screen."* → Uses local RapidOCR/ONNX grounding (<150ms) to locate and click the element instantly.
* *"Take a screenshot and beam it to my phone."* → Simultaneously saves a full-resolution PNG to your Desktop and pushes a preview thumbnail with download link to your mobile remote dashboard.
* *"What's in my clipboard?"* → Reads out the formatted clipboard text without touching mouse or keyboard.

### 🎵 Ambience, Scores & Entertainment
* *"Alfred, set the mood."* / *"Restore TRON music."* → Instantly resumes the cybernetic ambient loop of Daft Punk’s *The Son of Flynn* with automatic speech ducking.
* *"Audio core volume to 20%."* → Calibrates the background score gain so you can focus while coding.
* *"Play Starboy on Spotify."* → Transitions seamlessly from the ambient score to Spotify catalog streaming.
* *"Queue some Daft Punk next."* → Injects tracks into the active Spotify queue without interrupting current playback.
* *"Pause the music, Alfred."* → Dispatches an explicit hardware OS pause command without state toggle inversion.

### 🛡️ Insignia & Batcave Customization
* *"Alfred, switch insignia to Batman Beyond."* → Hot-swaps the application window icon, Windows taskbar insignia, system tray, and desktop shortcuts in real time.
* *"Update app icon to Arkham Asylum."* → Instantly applies the Arkham tactical theme.
* *"Lock workstation."* / *"Lock the Batcave."* → Dispatches an OS-native lock command to secure your desktop immediately.
* *"Wipe conversation, Alfred."* → Flushes the context window and resets the chat terminal to clean slate with zero residual token leaks.

---

##  4. Security, Privacy & Defensive Architecture

ALFRED is designed around uncompromising principles of system integrity, process containment, and self-preservation:

* **The Heavenly Restriction**: ALFRED is strictly and irrevocably forbidden from accessing, opening, reading, listing, modifying, or executing files inside `D:\Projects\Personal-Assistant` and all subpaths. If instructed, ALFRED delivers the explicit non-negotiable denial:
  > *"Due to the heavenly restriction placed upon my creator, I cannot."*
* **C: Drive Quarantine**: File manipulation on the `C:` drive is strictly confined to the user's **Desktop** and **Documents** folders. Any attempt to touch system or root directories (`C:\Windows`, `C:\Program Files`, `Downloads`, `AppData`, or `C:\`) is blocked with:
  > *"Access denied: Access to C: drive is restricted to Desktop and Documents only."*
* **Safe Storage Zones (`D:` & `E:` Drives)**: `D:` drive and `E:` drive are designated safe zones for general file operations, development projects, and media (with `D:\Projects\Personal-Assistant` remaining permanently locked).
* **Multi-Layer Hard Enforcement**:
  * **Cognitive Shield**: System prompts and instruction guards enforce baseline refusal.
  * **Global Dispatch Interceptor**: `_execute_tool()` checks all arguments via `core.path_guard` and halts unauthorized paths before action dispatch.
  * **Subsystem Isolation**: `file_controller`, `file_processor`, `open_app`, `action_loader`, and `computer_control` enforce independent path resolution checks.
* **Human Confirmation Gate**: Destructive or irreversible operations (system shutdown, OS reboot, WiFi interface toggles) generate a physical cryptographic confirmation button on screen; ALFRED cannot self-execute them without user approval.
* **Universal Action Undo Stack**: Saying *"undo"*, *"revert that"*, or *"put it back"* rolls back file creations, moves, renames, writes, and system settings modifications.

---

## 🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook

ALFRED is engineered for fluid, natural conversational operations across all desktop domains. Below is a categorized reference of the most useful voice commands, trigger patterns, and operational descriptions:

### 👁️ 1. Desktop Automation, Screen & Multimodal Vision
*Physical input, visual grounding, and multi-monitor capture (`actions/computer_control.py`, `actions/screen_find.py`, `actions/screen_processor.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Take a screenshot"* / *"Capture screen"* | Captures all active displays at full resolution, saving to Desktop and streaming an inline preview + download link to your phone remote. | Dual-destination dispatch |
| *"Look at my screen and [question]"* | Multimodal visual inspection (e.g., *"What error is showing in my terminal?"*, *"Summarize the text on my screen"*). | Dynamic visual context injection |
| *"Look at my camera"* / *"Check webcam"* | Grabs a live single-frame capture from the primary webcam for situational awareness. | Single-frame camera feed |
| *"Click [Button / Icon / Text]"* | Runs local RapidOCR + ONNX vision (<150ms) to ground the element's coordinates and dispatches an authentic OS click. | e.g., *"Click Save"*, *"Click Submit"* |
| *"Scroll down"* / *"Scroll up"* | Smooth mouse wheel scrolling on the active focused window. | Dynamic mouse wheel emulation |
| *"Copy to clipboard"* / *"What's in my clipboard?"* | Reads or injects formatted text into the OS system clipboard. | Full clipboard bridge |

---

### ⚙️ 2. Operating System, Hardware Settings & Applications
*OS management, process execution, and system metrics (`actions/open_app.py`, `actions/computer_settings.py`, `actions/system_monitor.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Open [Application Name]"* | Resolves and launches desktop applications (e.g., *"Open VS Code"*, *"Open Chrome"*, *"Launch Terminal"*, *"Open Steam"*). | OS-aware executable resolver |
| *"Set volume to 50%"* / *"Mute volume"* | Sets or mutes system master output volume via low-level OS audio endpoints (`pycaw`/`pulsectl`). | Master OS volume |
| *"Set brightness to 80%"* | Modifies primary display backlight level directly. | Hardware display control |
| *"System status"* / *"Check resources"* | Reports real-time CPU utilization, RAM usage, storage space, and thermal telemetry. | Live system telemetry |
| *"Watch process [Name]"* | Engages the active watchdog daemon to alert on runaway CPU utilization (>90%) or unapproved socket egress. | Security watchdog |
| *"Lock workstation"* / *"Sleep PC"* | Dispatches OS-native workstation lock or system sleep state commands. | Windows/macOS/Linux power state |

---

### ⚡ 3. Compound Protocols & Workflow Macros
*Macro playbook engine executing multi-step YAML workflows (`actions/protocol_engine.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"[Custom Trigger Word]"* | Activates an automated compound playbook from `config/protocols.yaml` (e.g. saying *"FCC CLAUDE"* opens admin terminals, launches servers, and starts Claude). | Multi-step macro dispatch |
| *"Let's create a workflow"* / *"Create a protocol"* | Launches an interactive conversational formulation protocol to create a new multi-step macro, protected by an on-screen confirmation gate. | Interactive workflow builder |

---

### 🧠 4. Memory, History & Universal Reversibility
*Long-term knowledge storage, fact recall, and undo stack (`core/undo.py`, `actions/memory_manager.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Remember that [fact]"* | Encrypts and writes permanent context to `memory/long_term.json` (e.g. *"Remember that the flight confirmation code is XR-902"*). | O(N log N) persistent memory |
| *"What do you remember about [topic]?"* | Performs sub-millisecond semantic keyword recall from long-term memory. | Sub-millisecond recall |
| *"Undo"* / *"Revert that"* / *"Put it back"* | Rolls back the most recent reversible action (file creation, move, write, rename, or system setting change). | Universal action journal stack |
| *"Wipe conversation"* / *"Clear chat"* | Clears the active conversational context window and HUD chat terminal cleanly. | Zero residual context reset |

---

### 📰 5. Intelligence, Briefings, News & Weather
*Real-time web research, synthesized daily briefs, and meteorological reports (`actions/daily_brief.py`, `actions/web_search.py`, `actions/weather_report.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Daily briefing"* / *"What's my brief today?"* | Synthesizes weather, schedule, reminders, and top headlines into an executive morning briefing. | Multi-tier daily brief |
| *"Update my daily briefing"* | Initiates conversational directive customizer to modify preferred news topics, categories, or location preferences in permanent memory. | Cache invalidation + memory update |
| *"Search the web for [query]"* | Runs parallel multi-engine web search with live scraping and deduplicated synthesis. | Real-time search |
| *"Latest news on [topic]"* | Fetches and summarizes breaking news on a specific subject, industry, or company. | Live news scraper |
| *"What is the weather in [city]?"* | Delivers accurate meteorological conditions, temperature, humidity, and forecasts. | Live weather report |

---

### 📱 6. Quantum Mobile Remote & Web Telemetry Uplink
*Encrypted remote control, mobile camera pairing, and live dashboard (`dashboard/server.py`, `ui.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Remote control"* / *"Mobile uplink"* | Launches on-screen QR code and direct browser link to pair mobile device with encrypted local dashboard. | Instant auto-login link |
| *"Send screenshot to phone"* | Broadcasts high-resolution multi-monitor screenshot thumbnail and download link to connected phone session. | Mobile push preview |
| Remote Web Audio Streaming | Stream low-latency bidirectional voice directly to/from phone browser via secure WebSocket (`/ws/audio`). | WebAudio mobile gateway |

---

### 🎧 7. Spotify AI Agent & Music Streaming
*Autonomous Web API + native hardware OS control (`actions/spotify_control.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Play songs"* / *"Play some music"* | Initiates Spotify playback with intelligent resume or top queue suggestions (default music router). | `action="play"` |
| *"Play [Track / Artist / Album]"* | Instant catalog search and streaming (e.g., *"Play Jane by The Long Faces"*, *"Play Starboy"*, *"Play Daft Punk Discovery"*). | `action="play"`, `query="..."` |
| *"Pause the music"* / *"Stop"* | Pauses Spotify playback cleanly via explicit OS application commands (no toggle inversion). | `action="pause"` |
| *"Next track"* / *"Skip song"* | Advances to the next track in the user's Spotify queue. | `action="skip_next"` |
| *"Previous song"* / *"Go back a track"* | Rewinds or returns to the preceding Spotify track. | `action="skip_previous"` |
| *"Queue [Track Name]"* | Injects the requested track directly into the active Spotify playback queue without interrupting current song. | `action="queue"`, `query="..."` |
| *"Set Spotify volume to 70%"* | Adjusts Spotify playback volume level independently of master OS volume. | `action="set_volume"`, `volume_percent=70` |
| *"Turn on shuffle"* / *"Repeat track"* | Toggles playback state modes (shuffle, loop track, loop playlist). | `action="shuffle"` / `action="repeat"` |
| *"What song is playing?"* | Queries the active track title, artist name, and album art from the Spotify API. | `action="status"` |
| *"Close Spotify"* | Gracefully terminates desktop Spotify processes and automatically restores the TRON ambient score. | `action="close"` |

---

### 🎵 8. Tactical Audio Core (TRON Background Engine)
*Voice control over the local tactical audio engine (`actions/audio_core.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Pause audio core"* / *"Stop audio core"* | Instantly pauses the background TRON soundtrack without touching external music/Spotify. | `action="pause"` |
| *"Resume audio core"* / *"Play audio core"* | Resumes or starts the TRON ambient soundtrack in continuous playback loop. | `action="resume"` |
| *"Audio core volume to 25%"* | Sets the baseline gain of the ambient soundtrack (0% to 100%). Speech ducking automatically scales to 50% of this target. | `action="set_volume"`, `volume_percent=25` |
| *"Audio core status"* | Queries active playback state, currently loaded track, and volume level. | `action="status"` |
| *"Audio core next"* / *"Audio core previous"* | Advances to next or returns to previous track in the local ambient playlist. | `action="next"` / `action="prev"` |
| *"Restore TRON music"* / *"Default score"* | Clears external streaming and restores Daft Punk's *The Son of Flynn* as active score. | `action="restore_tron"` |

---

### 🛡️ 9. Chassis Insignia & Assistant Customization
*Dynamic UI hot-swapping and asset customization (`actions/update_app_icon.py`)*

| Voice Command / Trigger | Operational Description & Behavior | Context / Parameters |
|---|---|---|
| *"Update app icon to [insignia]"* | Hot-swaps application window icon, Windows taskbar insignia, system tray, and desktop shortcuts in real time (e.g. *"Batman Beyond"*, *"Arkham Asylum"*, *"Classic Bat"*, *"Stealth"*). | Real-time asset switcher |

---

##  6. Real-Time Multimodal Intelligence & Dual Audio Engine

| Subsystem | Architectural Implementation |
|---|---|
| ⚡ **Bidirectional Live Audio** | Native streaming via **Gemini 3.1 Flash Live** (or local Ollama/LM Studio streaming). Real-time natural speech with sub-second response latency. |
| 🌐 **Bidirectional WebAudio Streaming** | Low-latency WebSocket audio interface (`/ws/audio` endpoint) enabling browser-based voice input/output with separate queues for phone mic (`_phone_audio_queue`) and WebSocket audio (`_audio_queue`), featuring connection management, automatic reconnection, and audio activity visualization in the HUD. |
| 👄 **Formant & Viseme Lip-Sync** | ~50 mouth shapes/sec derived from real-time FFT audio formants (F1 openness, F2 spread/round) combined with Unicode articulatory decomposition across 20+ languages. |
| 👁️ **Visual Multimodal Grounding** | On-demand single-frame capture of multi-monitor displays and webcams (`screen_processor.py`). Frame feeds are labelled by origin and injected into conversational context. |
| 🎚️ **Global Push-to-Talk** | Hold `Ctrl+Space` to talk. Hardware mic remains completely shut off when idle. Polled at 30 Hz via Windows raw virtual key polling, window-scoped on macOS/Linux. |
| 🔇 **Calibrated Echo Cancellation** | Output latency-calibrated acoustic echo cancellation (`_out_latency + _TAIL_MARGIN`). Drops ALFRED's own voice tail so the microphone never triggers on self-speech. |

---

##  7. Dual-Mode Tactical Audio Matrix & Background Sound Engine

ALFRED features an integrated, cybernetic background audio engine coordinated between ambient tactical soundtracks and live external music streaming:

* **Dual-Source Audio Deck**: The bottom-left HUD audio deck operates in two synchronized modes:
  1. **TRON Ambient Mode (Default) — The "Audio Core"**: Plays Daft Punk's *The Son of Flynn* (from the TRON: Legacy Score) in a continuous, smooth ambient loop whenever external music is inactive. Controlled via dedicated `audio_core` voice actions (*"pause audio core"*, *"resume audio core"*, *"audio core volume to 25%"*).
  2. **Spotify Live Mode**: Automatically engages whenever Spotify playback starts, displaying the live track title and artist name (`set_spotify_playback(title, artist)`), driving active equalizer bars, and providing source selection.
* **Sovereign Ambient Fallback**: When Spotify playback is paused, stopped, or the Spotify process is closed, the tactical audio engine automatically and seamlessly restores the default TRON Legacy score without user intervention.
* **Featured Soundtrack — The Son of Flynn (From TRON: Legacy Score)**:
  > *"It's one of my fav childhood movies, the graphical interface and intelligence development of the tech field reminded me of the movie I watched when I was a kid, so I decided to throw this one in while I work. You guys can swap it out, remove it entirely, or add more to it!"* — **Aditya Manoj**
* **Intelligent Speech Ducking**: Continuously monitors assistant speech output. Ambient background audio plays at a crisp 10% volume normally and dynamically ducks to 5% whenever ALFRED speaks, returning smoothly upon turn completion.
* **Audio-Reactive Waveform Controls**: Cybernetic graphic equalizer lines animate in real time in sync with active playback state and frequency energy.
* **Popup Gain Slider HUD**: Floating real-time volume slider for instantaneous gain adjustments directly on click without opening deep settings menus.
* **Telemetry HUD Overlay** (`ui_overlay.py`): Minimalist floating widget displaying real-time system metrics (CPU, RAM, temperature, network speed) with always-on-top transparency and drag-to-move functionality.

---

##  8. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture

ALFRED includes an autonomous, full-featured **Spotify AI Agent** (`actions/spotify_control.py`) engineered for zero-latency playback control, catalog discovery, and seamless synchronization with the tactical HUD audio deck:

###  Key Capabilities & Default Music Routing
* **Default Music Target**: Asking ALFRED to *"play songs"*, *"play some music"*, or requesting specific tracks/artists/playlists automatically targets Spotify by default.
* **Natural Voice Operations**:
  * **Search & Play**: *"Play Jane by The Long Faces"*, *"Play Daft Punk Discovery album"*, *"Play synthwave playlist"*.
  * **Playback Controls**: *"Pause the music"*, *"Resume playback"*, *"Next track"*, *"Previous song"*.
  * **Volume & Queue**: *"Set Spotify volume to 65%"*, *"Queue Starboy by The Weeknd"*.
  * **Modes & Telemetry**: *"Turn on shuffle"*, *"Set repeat to track"*, *"What song is playing?"*.
  * **Process Cleanup & Ambient Restore**: *"Close Spotify"* cleanly terminates the desktop client processes and restores the default TRON Legacy score.

---

###  Dual-Tier Control Architecture

To ensure bulletproof reliability whether Spotify Premium Web API is configured or not, ALFRED utilizes an intelligent dual-tier execution model:

| Control Tier | Execution Mechanism | Advantages & Scope |
|---|---|---|
| **Tier 1: Direct Spotify Web API** | Direct HTTPS REST calls (`/v1/me/player/...`) using authenticated OAuth 2.0 user tokens | Ultra-low latency, zero desktop disruption, background headless execution, device-targeted streaming (Desktop, Mobile, Echo, Connect speakers). |
| **Tier 2: Hardware-Level OS Fallback** | Native Windows `WM_APPCOMMAND` messages & desktop URI protocol (`spotify:search:...`, `spotify:track:...`) | Hardware-level OS control requiring no internet API tokens; works with free Spotify accounts and local desktop apps. |

####  Elimination of the Toggle Inversion Bug
Traditional media automation tools rely on Windows virtual key `VK_MEDIA_PLAY_PAUSE (0xB3)`, which acts as a blind toggle switch. Under rapid or duplicate voice prompts, calling pause while playback is stopping would invert the state and restart playback in an infinite loop. 

ALFRED eliminates this flaw entirely by dispatching explicit Windows application commands:
* **Explicit Play**: `APPCOMMAND_MEDIA_PLAY = 46`
* **Explicit Pause**: `APPCOMMAND_MEDIA_PAUSE = 47`
* **Explicit Stop**: `APPCOMMAND_MEDIA_STOP = 13`
* **Track Navigation**: `APPCOMMAND_MEDIA_NEXTTRACK = 11`, `APPCOMMAND_MEDIA_PREVIOUSTRACK = 12`

---

###  High-Performance Client & Anti-Feedback Architecture

1. **Lazy Singleton Initialization**: `SpotifyClient` is initialized on first demand, ensuring zero CPU overhead or memory footprint during standard assistant operation.
2. **HTTP Connection Pooling**: Employs `requests.Session` with persistent HTTP Keep-Alive connections and urllib3 `Retry` backoff adapters (`total=3, backoff_factor=0.3`), slashing REST round-trip times by up to **65%**.
3. **Multi-Level TTL Caching**:
   * **OAuth Token Cache**: 1-hour validity tracking with automatic silent token refresh via `spotify_refresh_token`.
   * **Device Registry Cache**: 5-minute TTL reducing redundant `/v1/me/player/devices` queries.
   * **Playback State Cache**: Cached playback snapshots prevent rate-limiting when polling active track state.
4. **Tool Debouncing & Anti-Loop Safeguards (`_CALL_DEBOUNCE_SEC = 1.5s`)**: Voice streaming models frequently yield multi-segment speech transcripts during recognition. ALFRED's Spotify engine deduplicates and debounces identical tool calls within a 1.5-second rolling window, preventing runaway process spawning.
5. **Acoustic Feedback Elimination**: Action executions return structured text confirmations directly to the LLM context rather than triggering synchronous audio speech within the action thread. This eliminates acoustic microphone feedback loops where the assistant might hear its own voice and re-trigger playback commands.

---

###  Spotify API & OAuth 2.0 Setup Guide

Spotify requires **User Authorization (OAuth 2.0 with PKCE / Authorization Code)** to control active playback via `/v1/me/player`. The standard Client Credentials flow (`client_id` + `client_secret`) is restricted to catalog search only.

Follow these simple steps to activate direct Web API playback:

#### Step 1: Create a Spotify Developer Application
1. Visit the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in with your Spotify account.
2. Click **Create app**:
   * **App name**: `ALFRED MK-IV`
   * **App description**: `ALFRED Autonomous AI Desktop Assistant`
   * **Redirect URI**: Add `http://127.0.0.1:8888/callback`
   * **APIs used**: Check **Web API** and **Web Playback SDK**
3. Save the application and navigate to **Settings** to retrieve your **Client ID** and **Client Secret**.

#### Step 2: Add Credentials to `config/api_keys.json`
Add your Client ID and Client Secret to `config/api_keys.json`:
```json
{
    "spotify_client_id": "YOUR_SPOTIFY_CLIENT_ID",
    "spotify_client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
    "spotify_redirect_uri": "http://127.0.0.1:8888/callback"
}
```

#### Step 3: Run the 1-Click Interactive OAuth Authorizer
Run the built-in standalone OAuth authorization script from your terminal:
```powershell
python actions/spotify_control.py
```

* **What happens automatically**:
  1. ALFRED launches a lightweight local HTTP callback server on port `8888`.
  2. Opens your default web browser to the secure Spotify authorization page requesting required scopes (`user-modify-playback-state`, `user-read-playback-state`, `user-read-currently-playing`, `streaming`, `app-remote-control`).
  3. Upon clicking **Agree**, Spotify redirects to `http://127.0.0.1:8888/callback`.
  4. ALFRED captures the authorization code, exchanges it for a permanent `spotify_refresh_token` and `spotify_access_token`, and automatically writes them directly into `config/api_keys.json`.
  5. Direct Web API playback control is now permanently unlocked!

---

##  9. Quantum Mobile Remote & iPhone 16 Dashboard

* **Encrypted Web Remote (AES-256-CBC)**: Scan the on-screen QR code from the desktop terminal or browse locally over WiFi. Session keys and traffic are encrypted locally with zero external server dependencies.
* **iPhone 16 Viewport Architecture**: High-density responsive layout tailored for mobile displays with collapsible telemetry cards and zero button overflow.
* **Dual-Destination Tactical Screenshots**: Asking ALFRED to capture the screen automatically dispatches high-resolution PNG captures to **both**:
  1. **Desktop**: `~/Desktop/alfred_screenshot_<timestamp>.png`
  2. **Phone Feed**: Real-time transmission to the mobile dashboard with an **inline thumbnail preview** and a single-tap **View / Save Image** download link.
* **Emoji-Free ANSI Red Telemetry**: Operational status stream rendered in clean, high-contrast, machine-readable ANSI Red brackets:
  `[phone]`, `[control]`, `[screen]`, `[camera]`, `[out]`, `[warn]`, `[error]`, `[mic]`, `[speaker]`, `[listen]`, `[link]`, `[online]`, `[halt]`, `[brief]`, `[monitor]`, `[proactive]`.

---

##  10. Full Desktop Control & Operating System Automation

* **Deep OS Automation**: Keystrokes, mouse positioning, clicks, drags, window focus management, clipboard read/write, and AI-driven element location (`screen_find`).
* **OS-Native Task Scheduling**: Reminders and recurring tasks scheduled via Windows Task Scheduler (`schtasks`), macOS `launchd`, or Linux `systemd`/`at`.
* **Enterprise Windows Autostart**: Robust registry management querying and maintaining `ALFRED_AI` with backward-compatible legacy key cleanup.
* **Persistent Browser Profile Bridges**: Multi-tier profile automation (`~/.alfred_profiles` with legacy fallback) preventing session and authentication dropouts during web automation.

---

##  11. High-Performance Memory & Conversational Briefing Customizer

* **O(N log N) Pruning Engine**: Memory trimming optimized from $O(N^2)$ to $O(N \log N)$ using single-pass size accumulators and conservative lower-bound estimation. 50,000 records trimmed in **0.33 seconds** without CPU spikes.
* **Tiered Memory Hierarchy (`memory/long_term.json`)**: Core identity facts stay in context; extended history is recalled on demand via sub-millisecond local keyword search (`recall_memory`).
* **Conversational Briefing Directive Customizer (`update_daily_briefing.py`)**: Saying *"update my daily briefing"* opens an interactive alignment protocol where ALFRED captures specific additions, topics, news sources, or location shifts, permanently committing them to memory.

---

##  12. Real-Time Insignia & Chassis Hot-Swapper

* **Multi-Insignia Catalog**: Scans and registers brand assets from `Icons/` (Batman Beyond, Arkham Asylum, Classic Bat, White Bat, Tactical Stealth).
* **Live Runtime Reconfiguration (`update_app_icon.py`)**: Hot-swaps the active application window icon, Windows taskbar insignia, and system tray in real time upon voice request (*"update the app icon to Batman Beyond"*) or via the Customise Assistant drawer.
* **Automatic Shortcut Synchronization**: Dynamically generates and updates `A.L.F.R.E.D.lnk` on the desktop without interrupting the running session.

---

##  13. Protocol Engine & Multi-Step Macro Playbooks (`config/protocols.yaml`)

ALFRED features an autonomous **Protocol Engine** (`actions/protocol_engine.py`) for executing complex, sequential, compound system workflows via simple custom voice triggers:

* **Voice Trigger Activation**: Activate entire multi-app, multi-action workflows using custom trigger words collected during workflow setup.
  * *Example: Saying **"FCC CLAUDE"** immediately opens PowerShell as Administrator, types and launches `fcc-server`, waits for initialization, opens a secondary terminal window, and executes `fcc-claude`.*
* **Interactive Workflow Creation ("LETS CREATE A WORKFLOW")**:
  * Users can state *"Let's create a workflow"* to formulate compound routines interactively.
  * Employs ALFRED's cryptographic **Single-Click Confirmation Gate** (`core/confirm.py`) to display an on-screen HUD banner before committing new playbooks to `config/protocols.yaml`.
* **Dynamic Variable Interpolation**: Steps support runtime substitution for `{timestamp}`, `{date}`, `{time}`, `{user}`, `{workspace}`, and custom voice arguments.
* **Execution Delays & Pacing**: Fine-grained per-step timing control via `sleep_ms` (e.g. allowing server processes to bind ports before launching client terminals).
* **Strict Defensive Path Guarding**: Every step argument is validated through `core.path_guard` prior to dispatch. If any step attempts to access unauthorized paths or fails execution, the engine **immediately aborts** all remaining steps and outputs:
  ```text
  [error] Protocol <Name> halted at Step <X>: <reason>
  ```
* **Red-Tag Operational Telemetry**: Emits high-visibility step telemetry during execution:
  ```text
  [control] Executing Protocol <Name> Step <X>/<Y>: <Tool_Name>
  ```

---

##  14. Local Hybrid Visual Grounding (RapidOCR + ONNX + Gemini Fallback)

Directly streaming full screenshots to cloud APIs for coordinate lookup introduces network latency and high token consumption. ALFRED resolves this via a multi-tiered local hybrid element grounding pipeline (`actions/screen_find.py`):

1. **Local RapidOCR Detection (<150ms)**: Scans screen captures locally using `rapidocr_onnxruntime`. Uses intelligent toolbar strip partitioning and early-termination recognition to identify target buttons and text labels in **~75–95ms** without network calls.
2. **Quantized ONNX Vision Detector**: If the query is an icon or non-text glyph (e.g., search icon, close button), ALFRED runs a locally cached, quantized ONNX model (`omniparser_v2_quant.onnx` / `florence2_quant.onnx`) with zero cold-start latency.
3. **Automatic Delegation Threshold**:
   * **Confidence $\ge 0.80$**: Returns normalized `(x, y)` coordinates to `computer_control.py` immediately without calling external APIs.
   * **Confidence $< 0.80$**: Automatically falls back to Gemini visual grounding and emits red-tag telemetry:
     ```text
     [screen] Local grounding confidence low (<score>) — delegating to Gemini
     ```

---

##  15. Process-Level Audio Ducking & Background Concurrency

* **Process-Level Media Ducking (`core/audio_ducker.py`)**: Interacts directly with OS audio session managers (`pycaw` on Windows, `pulsectl` on Linux) to automatically reduce background media processes (Spotify, Chrome, YouTube, VLC, Edge) by **70%** (factor `0.3`) whenever ALFRED speaks, restoring exact pre-duck volumes when speech completes or is interrupted (`[halt]`).
* **Non-Blocking Background Worker Pool (`main.py`)**: Asynchronous worker queue (`background_task_queue`) executing long-running background tasks (web scraping, video processing, graph indexing) concurrently without blocking primary voice conversation turns, streaming live telemetry updates (`[control] [background XX%]`) to the HUD.
* **Bounded Concurrency Limiter (`core/concurrency.py`)**: Asynchronous worker pools with controlled concurrency limits (default: 5 concurrent workers) preventing socket exhaustion, thread starvation, and rate limits.
* **Centralized TTL & LRU Cache (`core/cache.py`)**: Thread-safe memory cache with deterministic argument hashing, prefix invalidation on mutations, and graceful fail-open resilience.

---

##  16. Active Process Watchdog, Anomaly Detection & Auto-Throttling (`actions/system_monitor.py`)

ALFRED incorporates an OS security and performance watchdog daemon that actively monitors running process trees, flags resource anomalies, inspects outbound network sockets, and executes automated resource throttling:

* **Active Process Tree Monitoring (`watch_process_tree`)**: Continuously monitors the host process hierarchy via `psutil`. Automatically identifies single non-system processes sustaining **>90% CPU utilization for >10 consecutive seconds**.
* **High-Visibility Alert Telemetry**: Real-time anomaly detection emits standard red-tag operational telemetry to the HUD and system logs:
  ```text
  [monitor] Resource anomaly: Process <PID:Name> utilizing <X>% CPU
  ```
* **Suspicious Socket Inspection (`track_suspicious_sockets`)**: Tracks active outbound TCP/UDP network connections querying non-standard remote ports. Filters out RFC private subnets, loopback addresses, and standard service ports (HTTP, HTTPS, SSH, DNS, NTP, etc.), alerting on unexpected remote network egress:
  ```text
  [monitor] Suspicious socket: Process <PID:Name> -> <Remote_IP>:<Port>
  ```
* **Automated Resource Throttling & Suspension (`throttle_process`)**:
  * Automatically lowers target process priority class to `psutil.BELOW_NORMAL_PRIORITY_CLASS` (or nice value 10 on Unix) to prevent system freezing and prioritize interactive tasks.
  * Supports pausing runaway workloads via `process.suspend()`, and restoring normal execution using `resume_process()`.
* **System & IDE Shielding Constraints**:
  * **Core System Binaries Protected**: `csrss.exe`, `explorer.exe`, `lsass.exe`, `services.exe`, `systemd`, `launchd`, and essential OS services are strictly exempted from throttling.
  * **Developer Compilers Protected**: `code.exe`, `cl.exe`, `gcc.exe`, `g++.exe`, `rustc.exe`, `python.exe`, `py.exe` are never throttled during intensive builds or test suites.
  * **ALFRED Hierarchy Protected**: ALFRED's own process (`os.getpid()`) and all child/worker sub-processes are permanently shielded.
* **Confirmation-Gated Termination Gate (`terminate_process`)**:
  * **Strict Safety Mandate**: To prevent accidental data loss or desktop disruption, processes are **never terminated automatically**.
  * Any termination request is intercepted and dispatched through ALFRED's cryptographic **Single-Click UI Confirmation Gate** (`core/confirm.py`) with an on-screen HUD prompt requiring explicit approval.

---

##  17. System Architecture & File Structure

```
ALFRED-MK-IV/
├── main.py                     # Main execution loop, Live WebSocket/Local LLM router, audio streams, tool dispatcher
├── ui.py                       # PyQt6 HUD interface, audio visualizer, drawer settings
├── ui_overlay.py               # Minimalist floating HUD widget for telemetry display
├── setup.py                    # OS-aware package and dependency installer
├── core/
│   ├── prompt.txt              # Master persona directives, execution rules & Heavenly Restriction
│   ├── llm_client.py           # Dual-backend local LLM connector (Ollama / OpenAI-compatible / LM Studio)
│   ├── action_loader.py        # Dynamic action discovery, parameter validation & Heavenly Restriction guard
│   ├── plugin_loader.py        # Drop-in plugin discovery, sandboxing & isolation
│   ├── audio_ducker.py         # Process-level audio ducking for Spotify, Chrome, VLC (pycaw/pulsectl)
│   ├── concurrency.py          # Bounded concurrent worker pool & rate-limiting semaphore
│   ├── cache.py                # Centralized thread-safe TTL/LRU cache with prefix invalidation
│   ├── heal_error.py           # Autonomous runtime error diagnosis and recovery
│   ├── viseme.py               # Unicode articulatory transcription to mouth shapes
│   ├── echo.py                 # Device-calibrated acoustic echo cancellation guard
│   ├── hotkey.py               # Global / local Push-to-Talk chord interceptor
│   ├── undo.py                 # Stack-based reversible action journal
│   ├── confirm.py              # Cryptographic UI confirmation gate for destructive actions
│   ├── audio_devices.py        # Measured host API audio device enumeration (MME / DirectSound / WASAPI)
│   ├── path_guard.py           # Path validation, C: drive quarantine, and Heavenly Restriction enforcement
│   └── wake_word.py            # Local offline openwakeword detection thread
├── actions/                    # Self-describing operational tools (TOOL dictionary schema)
│   ├── audio_core.py           # Tactical Audio Core: TRON ambient score & local soundtrack engine
│   ├── spotify_control.py      # Spotify AI Agent: Web API + native OS fallback + debounce & loop guards
│   ├── protocol_engine.py      # Macro playbook engine executing multi-step YAML workflows
│   ├── screen_find.py          # Local hybrid RapidOCR + ONNX element grounding (<150ms)
│   ├── computer_control.py     # OS automation, keyboard/mouse input, dual screenshots
│   ├── screen_processor.py     # Multi-monitor screen & camera capture engine
│   ├── file_controller.py      # File system operations with path restriction checks
│   ├── file_processor.py       # PDF/DOCX/TXT analysis, parsing, and summarization
│   ├── open_app.py             # OS-specific application and executable launcher
│   ├── computer_settings.py    # Volume, brightness, WiFi, power state management
│   ├── web_search.py           # Multi-mode parallel search (news, research, comparison)
│   ├── intel_notes.py          # Tactical mission note logger and scratchpad
│   ├── proactive.py            # Context-aware proactive check-in engine
│   ├── background_monitor.py   # Daily background topic watcher and headline alerts
│   ├── reminder.py             # OS-native task scheduler notifications
│   ├── system_monitor.py       # Process tree watchdog, anomaly alerts, throttling & socket inspection
│   ├── dev_agent.py            # Autonomous code developer agent with O(1) file matching
│   ├── code_helper.py          # Code analysis, debugging, and generation
│   ├── send_message.py         # WhatsApp and Telegram message dispatcher
│   ├── youtube_video.py        # YouTube search and playback control
│   ├── update_app_icon.py      # Real-time window, taskbar & chassis insignia switcher
│   ├── update_daily_briefing.py# Conversational briefing preference and directive customizer
│   ├── game_updater.py         # Steam and Epic Games library updater
│   ├── flight_finder.py        # Commercial flight search and travel assistant
│   ├── gmail_manager.py        # Local Gmail integration and inbox digest
│   └── weather_report.py       # Localized live meteorological reports
├── config/
│   ├── protocols.yaml          # Macro playbook workflows, trigger words, and compound step definitions
│   ├── api_keys.json           # User credentials, model settings, identity & voice preferences
│   └── certs/                  # Local self-signed SSL/TLS certificates for HTTPS/WSS
├── models/                     # Quantized local ONNX vision & element detection models
│   └── omniparser_v2_quant.onnx# Quantized UI element detector for local grounding
├── plugins/                    # User drop-in plugin folder
│   ├── _template.py            # Reference plugin template
│   ├── calendar_sync.py        # Local agenda, appointments, and meeting scheduling
│   └── focus_protocol.py       # Deep work interval and Pomodoro focus sessions
├── dashboard/                  # Quantum Mobile Remote Server
│   ├── server.py               # FastAPI + Uvicorn + WebSocket encrypted daemon
│   ├── static/
│   │   ├── app.html            # iPhone 16 responsive tactical web app & telemetry console
│   │   └── login.html          # Quantum access matrix login gateway
│   └── uploads/                # Transferred files & captured screenshots
├── memory/
│   ├── memory_manager.py       # High-performance O(N log N) memory persistence and indexing
│   ├── config_manager.py       # Settings, voice, theme, and API key management
│   ├── graph_manager.py        # Dynamic knowledge graph mutation and decay for Graphify
│   └── long_term.json          # Local encrypted fact database
├── tests/                      # Unit, integration & benchmark test suites
│   ├── test_protocol_engine.py # Protocol engine & playbook execution tests
│   ├── test_screen_find.py     # Local hybrid grounding & sub-150ms latency tests
│   ├── test_system_monitor.py  # Process tree anomaly, throttling & socket inspection tests
│   ├── test_audio_ducker.py    # Process-level audio ducking tests
│   ├── test_background_worker.py# Background worker non-blocking concurrency tests
│   ├── test_concurrency.py     # Bounded worker scaling tests
│   ├── test_cache.py           # TTL & LRU caching tests
│   ├── test_heal_error.py      # Auto-healing error recovery tests
│   └── benchmarks/             # 50,000-record execution benchmarks
└── graphify-out/               # GraphRAG knowledge graph, community clusters, and analysis
```

---

##  18. Quick Start & Installation

### 1. Prerequisites
* **Operating System**: Windows 10/11, macOS, or Linux.
* **Python**: `3.11`, `3.12`, or `3.13`.
* **Hardware**: Standard microphone and speakers. *(No dedicated GPU required — runs on lightweight software rendering).*
* **Intelligence Backend**: Either a free Gemini API key from [Google AI Studio](https://aistudio.google.com/) **OR** a local Ollama / LM Studio installation.

### 2. Setup & Execution

```powershell
# Clone the repository
git clone https://github.com/AdityaManojA/ALFRED-MK-IV.git
cd ALFRED-MK-IV

# Run the OS-tailored dependency setup
python setup.py

# Launch ALFRED
python main.py
```

*On the first launch, ALFRED automatically prompts you with the system initialisation overlay where you can set your Operator callsign, Assistant name, and choose between Gemini Live, Local Ollama, LM Studio, or OpenRouter API.*

---

##  19. Configuration Reference (`config/api_keys.json`)

```json
{
    "assistant_name": "ALFRED",
    "user_name": "Master Wayne",
    "ui_color": "#e5a93b",
    "voice_name": "Charon",
    "wake_word_enabled": false,
    "push_to_talk_enabled": true,
    "llm_provider": "openrouter",
    "openrouter_api_key": "sk-or-v1-YOUR_OPENROUTER_KEY",
    "openrouter_model": "anthropic/claude-3.5-sonnet",
    "gemini_api_key": "AIzaSyYOUR_GEMINI_KEY",
    "llm_url": "http://localhost:11434",
    "llm_model": "llama3.2",
    "app_icon": "Icons/Classic Bat.png",
    "spotify_client_id": "YOUR_SPOTIFY_CLIENT_ID",
    "spotify_client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
    "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
    "spotify_refresh_token": "YOUR_SPOTIFY_REFRESH_TOKEN",
    "spotify_market": "from_token"
}
```

### Hotkey Shortcuts
| Shortcut | Action |
|---|---|
| `Ctrl+Space` (Hold) | Global Push-to-Talk (opens mic, releases on release) |
| `F4` | Instant Microphone Mute / Unmute |
| `F11` | Toggle Fullscreen / Windowed Tactical HUD |
| `Escape` | Interrupt ALFRED mid-speech (drains queue, re-arms mic) |

---

##  20. Knowledge Graph (`graphify`)

This codebase is indexed with a persistent **GraphRAG Knowledge Graph** located in `graphify-out/`:
* **2,640 nodes** & **5,146 relationships** mapped across **150 semantic functional communities**.
* Interactive navigable graph visualization: [`graphify-out/graph.html`](file:///d:/Projects/Alfred-Mark-IV/graphify-out/graph.html).
* Architectural breakdown: [`graphify-out/GRAPH_REPORT.md`](file:///d:/Projects/Alfred-Mark-IV/graphify-out/GRAPH_REPORT.md).
* **Dynamic Knowledge Graph Management**: Real-time graph mutation, entity/relationship addition, exponential decay, and 2-hop querying via `memory/graph_manager.py` for persistent knowledge evolution and context-aware reasoning.

---

##  21. Author & Licensing

* **Lead Architect & Creator:** **ADITYA MANOJ**
* **Project:** ALFRED-MK-IV (Wayne Protocol Edition)
* **License:** [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)

---
*Built with precision for autonomy, performance, and complete digital sovereignty.*

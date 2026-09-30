# ALFRED on macOS — Siri-style mode

ALFRED on a Mac runs as two processes:

```
┌───────────────────────────── ALFRED.app ─────────────────────────────┐
│ alfredd  (Swift, mac/alfredd/)       started at login by launchd      │
│   • mic via the HAL, 4096-frame IO buffer        ≈0.03 % of one core  │
│   • energy VAD → on-device speech recognizer only while someone talks │
│   • "Hey Alfred" → chime → records the request → starts/wakes agent   │
│   • owns alarms & timers (they ring even when the agent is closed)    │
│   • unix socket ~/Library/Application Support/ALFRED/alfredd.sock     │
└───────────────┬───────────────────────────────────────────────────────┘
                │ spawns (so macOS permissions belong to ALFRED.app)
┌───────────────▼─────────────── Python agent (main.py) ────────────────┐
│ Gemini Live session, HUD, tools (actions/mac_*.py, browser_tabs.py)   │
│ idle 2 min → disconnects, releases mic ("dormant")                    │
│ dormant 15 min → exits; alfredd keeps listening                       │
└───────────────────────────────────────────────────────────────────────┘
```

## Install / update

```bash
conda activate alfred
pip install -r requirements.txt
mac/build.sh            # builds ALFRED.app into ~/Applications and starts it at login
```

macOS then asks ALFRED for **Microphone** and **Speech Recognition**. Other
permissions are requested the first time a feature needs them: Calendars,
Reminders, Contacts, Automation (per app: Chrome, Safari, Music, Notes,
Messages, Mail, System Events), Accessibility (media keys, keyboard control) and
Screen Recording (screenshots, vision).

The app is ad-hoc signed, so **every rebuild counts as a new app** and those
permissions are asked for again.

Remove the login agent with `mac/build.sh --uninstall`.

## Using it

* Say **“Hey Alfred”** (a soft *tink* confirms), then your request. You can say
  it in one breath or pause for the chime. The request is replayed to Gemini as
  audio, so any language Gemini understands works.
* Open **ALFRED** from Spotlight/Launchpad for the full HUD. Closing the window
  puts ALFRED to sleep instead of quitting; ⌘Q quits the agent.
* The bat icon in the menu bar: *Show ALFRED*, *Talk now*, *Sleep now*,
  *Pause/Resume “Hey Alfred”*, *Quit*.
* `mac/alfredctl` — `status`, `say "…"` (as if spoken), `show`, `pause`,
  `resume`, `alarms`, `stop`.

## What it can do on the Mac

| Tool | Examples |
|---|---|
| `mac_system` | volume/mute, exact brightness, sleep, lock, display off, restart/shutdown (confirms), dark mode, Night Shift, Wi-Fi, Bluetooth, battery, keep awake, screenshot |
| `mac_apps` | open / quit / force quit / hide / switch apps, what's running |
| `mac_media` | play/pause/next for Music, Spotify or any Now Playing app, now playing, play from the Music library, pause everything |
| `browser_tabs` | list / switch / open / close / reload tabs in Safari, Chrome, Brave, Edge, Arc, Vivaldi, Opera (Firefox: open, list, switch); **play_youtube** pauses every other YouTube video |
| `mac_calendar` | today/tomorrow/this week, search, create events with alerts, delete (confirms) |
| `mac_reminders` | list, add with due time (alerts on iPhone too), complete, delete |
| `mac_alarm` | alarms (one-off or repeating), timers, list, cancel, stop, snooze |
| `mac_notes` | create, search, read, append |
| `mac_messages` | iMessage / SMS (reads back and confirms), FaceTime audio/video, iPhone calls |
| `mac_mail` | unread summary, drafts, send (confirms) |
| `mac_contacts` | look up numbers and emails |
| `mac_maps` | directions, place search |
| `mac_shortcuts` | list and run the user's Shortcuts: Focus / Do Not Disturb, HomeKit scenes, Clock alarms, anything Siri can do through Shortcuts |

### Browser video control needs one switch per browser

Pausing and playing videos inside tabs runs a line of JavaScript through the
browser's AppleScript bridge, which browsers keep off by default:

* **Chrome / Brave / Edge / Arc / Vivaldi:** *View → Developer → Allow JavaScript from Apple Events* (per profile).
* **Safari:** *Settings → Advanced → Show features for web developers*, then *Develop → Developer Settings… → Allow JavaScript from Apple Events*.

Tab listing, switching and opening work without it.

Once it is on, every YouTube tab ALFRED touches also pauses itself whenever
another YouTube tab in the same browser starts playing (a `BroadcastChannel`
listener, no polling). The HUD's own player pauses browser YouTube when it
starts, and `play_youtube` pauses the HUD.

## Tuning

`~/Library/Application Support/ALFRED/daemon.json` (restart with
`launchctl kickstart -k gui/$(id -u)/local.alfred.assistant`, no rebuild):

| Key | Default | Meaning |
|---|---|---|
| `listening` | `true` | wake word on/off (alarms ring regardless) |
| `wakeWords` | `[]` | extra wake words (the assistant name from settings is added automatically) |
| `locale` | system | recognizer locale, e.g. `en-US`; falls back to en-US if the model is missing |
| `vadRatio` | `3.5` | how far above the room's noise floor counts as speech |
| `outputRatio` | `1.6` | extra strictness while the Mac is playing audio |
| `minLevel` | `0.0025` | absolute level below which nothing counts as speech |
| `debug` | `false` | log onsets and what the recognizer heard (local log only) |

`config/api_keys.json`: `mac_dormant_after_s` (default 120) and
`mac_exit_after_s` (default 900, `0` = stay loaded).

Logs: `~/Library/Logs/ALFRED-daemon.log` (listener) and `~/Library/Logs/ALFRED.log` (agent).
`kill -USR1 <agent pid>` dumps every Python thread's stack into the agent log.

## Limits

* Third-party apps can't use the always-on audio chip that "Hey Siri" uses, so
  the microphone indicator stays on while ALFRED listens. Pause listening from
  the menu bar icon when you want it off.
* Alarms ring only while the Mac is awake (lid open). A sleeping Mac rings
  missed alarms on wake if they are less than 10 minutes late.
* **Clock app alarms need one shortcut.** macOS only lets Apple-signed processes
  write Clock alarms (`mobiletimerd` rejects others as "not entitled"), and
  generating a shortcut file needs an iCloud-signed-in Mac. Create it once in
  Shortcuts: new shortcut named **ALFRED Set Alarm** → action *Clock ▸ Create
  Alarm* → set its time to *Shortcut Input*. Optionally add **ALFRED List
  Alarms** with *Clock ▸ Get All Alarms*. With it, one-off alarms within 24 h
  go into Clock; repeating/dated alarms and timers stay ALFRED alarms, which
  ring from ALFRED. Clock alarms can't be deleted from ALFRED (it opens Clock).

// alfredd — ALFRED's always-on listener for macOS.
//
// Runs at login (LaunchAgent) as ALFRED.app's main executable. It listens for
// "Hey Alfred" at ~0.03 % of one core, starts/wakes the Python agent on demand,
// and owns alarms/timers. While the agent is active the microphone is released
// here and belongs to the agent; when the agent goes dormant or exits, this
// picks it back up.
import AVFAudio
import AudioToolbox
import Foundation
import Speech

setvbuf(stdout, nil, _IOLBF, 0)
try? FileManager.default.createDirectory(at: Paths.support, withIntermediateDirectories: true)

let daemonMode = CommandLine.arguments.contains("--daemon")

// ── Single instance: a second launch (Finder, Spotlight, Dock) just asks the
// running daemon to show ALFRED, then leaves.
let lockFD = open(Paths.lock, O_CREAT | O_RDWR, 0o600)
if lockFD < 0 || flock(lockFD, LOCK_EX | LOCK_NB) != 0 {
    if !daemonMode { _ = sendToRunningDaemon(["type": "show"]) }
    exit(0)
}

final class Coordinator {
    let q = DispatchQueue(label: "alfredd", qos: .userInitiated)
    var config = DaemonConfig.load()
    lazy var mic = Mic(queue: q)
    lazy var wake = WakeEngine(queue: q)
    lazy var ipc = IPCServer(queue: q)
    lazy var alarms = AlarmStore(queue: q)
    lazy var ringer = Ringer(queue: q)
    lazy var agent = AgentManager(queue: q, config: { [unowned self] in self.config })
    lazy var output = OutputWatcher(queue: q)
    var statsTimer: DispatchSourceTimer?
    var permissionsOK = false
    var chime: SystemSoundID = 0

    func start(showAgent: Bool) {
        log("alfredd starting (pid \(getpid()), \(daemonMode ? "login agent" : "opened by user"))")
        var sid: SystemSoundID = 0
        if AudioServicesCreateSystemSoundID(URL(fileURLWithPath: "/System/Library/Sounds/Tink.aiff") as CFURL, &sid) == noErr {
            chime = sid
        }

        mic.onChunk = { [unowned self] ptr, n, rms in
            let samples = Array(UnsafeBufferPointer(start: ptr, count: n))
            let rate = self.mic.sampleRate
            self.q.async { self.wake.feed(samples, rms: rms, rate: rate) }
        }
        wake.onWake = { [unowned self] in self.wakeHeard() }
        wake.onCommand = { [unowned self] text, audio in self.commandHeard(text, audio: audio) }
        wake.onUtterance = { [unowned self] text in self.heardWhileRinging(text) }
        agent.onStateChange = { [unowned self] in self.updateCapture() }
        ringer.onStateChange = { [unowned self] in
            self.wake.transcribeAll = self.ringer.ringing != nil
            self.updateCapture()
        }
        alarms.onFire = { [unowned self] a in
            self.ringer.ring(a)
            self.agent.send(["type": "alarm_fired", "alarm": a.json()])
        }
        ipc.onMessage = { [unowned self] conn, msg in self.handle(conn, msg) }
        ipc.onClose = { [unowned self] conn in if conn.isAgent { self.agent.detach(conn) } }

        q.sync {
            if !ipc.start(path: Paths.socket) { log("ipc: could not listen on \(Paths.socket)") }
            alarms.arm()
            wake.configure(locale: config.locale, extraWords: config.wakeWords ?? [],
                           assistantName: config.assistantName, vadRatio: config.vadRatio,
                           outputRatio: config.outputRatio, minLevel: config.minLevel,
                           debug: config.debug ?? false)
            output.onChange = { [unowned self] busy in self.wake.outputActive = busy }
            output.start()
            // One line every 10 minutes, only when the recognizer actually ran.
            let t = DispatchSource.makeTimerSource(queue: q)
            t.schedule(deadline: .now() + 600, repeating: 600, leeway: .seconds(30))
            t.setEventHandler { [unowned self] in
                let (sessions, abandoned, wakes) = self.wake.takeStats()
                if sessions > 0 {
                    log("wake: last 10 min — \(sessions) recognizer sessions, \(abandoned) abandoned, \(wakes) wakes")
                }
            }
            t.resume()
            statsTimer = t
        }
        requestPermissions {
            self.q.async {
                self.updateCapture()
                if showAgent { self.show() }
            }
        }
    }

    func requestPermissions(_ done: @escaping () -> Void) {
        AVAudioApplication.requestRecordPermission { micOK in
            SFSpeechRecognizer.requestAuthorization { status in
                let speechOK = status == .authorized
                log("permissions: microphone \(micOK ? "granted" : "DENIED"), speech recognition \(speechOK ? "granted" : "DENIED (\(status.rawValue))")")
                self.permissionsOK = micOK && speechOK
                if !self.permissionsOK {
                    osascript("display notification \"Allow Microphone and Speech Recognition for ALFRED in System Settings → Privacy & Security, then reopen ALFRED.\" with title \"ALFRED can't hear “Hey Alfred”\"")
                }
                done()
            }
        }
    }

    // MARK: capture policy

    func updateCapture() {
        let listening = config.listening ?? true
        let agentFree = agent.state == .none || agent.state == .dormant
        let want = permissionsOK && ((listening && agentFree) || wake.busy || ringer.ringing != nil)
        if want && !mic.running {
            if !mic.start() { log("mic: could not start") }
        } else if !want && mic.running {
            mic.stop()
            wake.reset()
        }
    }

    // MARK: wake flow

    func wakeHeard() {
        log("wake: heard wake word")
        if ringer.ringing != nil { ringer.stop(); return }
        AudioServicesPlaySystemSound(chime)
        // Start loading the agent while the user is still speaking the command.
        agent.ensureRunning(reason: "voice")
        agent.send(["type": "wake", "source": "voice", "capturing": true])
        if agent.state == .dormant { agent.setState(.starting) }
    }

    func commandHeard(_ text: String, audio: [Int16]) {
        var msg: [String: Any] = ["type": "command", "text": text]
        if audio.count > 1600 {
            // Hand the recording over as a file; the socket stays small and text-only.
            let url = Paths.support.appendingPathComponent("utterance-\(Int(Date().timeIntervalSince1970 * 1000)).pcm")
            let data = audio.withUnsafeBufferPointer { Data(buffer: $0) }
            if (try? data.write(to: url, options: .atomic)) != nil {
                chmod(url.path, 0o600)
                msg["audio"] = url.path
                msg["rate"] = 16000
            }
        }
        log(String(format: "wake: command \"%@\" + %.1f s of audio", text, Double(audio.count) / 16000))
        agent.send(msg)
        updateCapture()
    }

    func heardWhileRinging(_ text: String) {
        guard ringer.ringing != nil else { return }
        let words = Set(WakeEngine.normalize(text))
        if words.contains("snooze") {
            snooze(minutes: 9)
        } else if !words.isDisjoint(with: ["stop", "cancel", "dismiss", "enough", "off", "up", "okay", "ok", "quiet"]) {
            ringer.stop()
        }
    }

    func snooze(minutes: Double) {
        guard let current = ringer.ringing else { return }
        ringer.stop()
        let a = Alarm(id: UUID().uuidString.prefix(8).lowercased(), kind: current.kind,
                      label: current.label.isEmpty ? "Snoozed" : current.label + " (snoozed)",
                      hour: nil, minute: nil, days: [],
                      fireAt: Date().timeIntervalSince1970 + minutes * 60, enabled: true)
        alarms.add(a)
        log("alarm: snoozed \(Int(minutes)) min")
    }

    func show() {
        if ringer.ringing != nil { ringer.stop() }
        agent.ensureRunning(reason: "show")
        agent.send(["type": "show"])
    }

    // MARK: IPC

    func handle(_ conn: Conn, _ msg: [String: Any]) {
        let type = msg["type"] as? String ?? ""
        var reply: [String: Any] = ["type": "reply", "ok": true]
        if let req = msg["req"] { reply["req"] = req }

        switch type {
        case "hello":
            if (msg["role"] as? String) == "agent" {
                agent.attach(conn)
                conn.send(["type": "welcome", "listening": config.listening ?? true,
                           "ringing": ringer.ringing?.json() ?? NSNull()])
            }
            return
        case "state":
            if let s = msg["state"] as? String, let st = AgentManager.State(rawValue: s) { agent.setState(st) }
            return
        case "show":
            show()
        case "inject":
            // mac/alfredctl: behave as if the text had been spoken after "Hey Alfred".
            let text = msg["text"] as? String ?? ""
            agent.ensureRunning(reason: "voice")
            agent.send(["type": "wake", "source": "inject", "capturing": false])
            agent.send(["type": "command", "text": text])
            if agent.state == .dormant { agent.setState(.starting) }
        case "listening":
            if let on = msg["enabled"] as? Bool {
                config.listening = on
                config.save()
                log("listening \(on ? "resumed" : "paused")")
                updateCapture()
            }
            reply["listening"] = config.listening ?? true
        case "status":
            reply["listening"] = config.listening ?? true
            reply["mic"] = mic.running
            reply["agent"] = agent.state.rawValue
            reply["ringing"] = ringer.ringing?.json() ?? NSNull()
            reply["alarms"] = alarms.list()
        case "alarm_add":
            guard let fireAt = msg["fire_at"] as? Double else {
                reply["ok"] = false; reply["error"] = "fire_at (epoch seconds) required"; break
            }
            let a = Alarm(id: String(UUID().uuidString.prefix(8)).lowercased(),
                          kind: msg["kind"] as? String ?? "alarm",
                          label: msg["label"] as? String ?? "",
                          hour: msg["hour"] as? Int, minute: msg["minute"] as? Int,
                          days: msg["days"] as? [Int] ?? [], fireAt: fireAt, enabled: true)
            alarms.add(a)
            reply["alarm"] = a.json()
            log("alarm: added \(a.kind) '\(a.label)' at \(a.json()["fire_at_local"] ?? "")")
        case "alarm_list":
            reply["alarms"] = alarms.list()
            reply["ringing"] = ringer.ringing?.json() ?? NSNull()
        case "alarm_cancel":
            reply["removed"] = alarms.remove(id: msg["id"] as? String ?? "")
        case "alarm_stop":
            reply["was_ringing"] = ringer.ringing != nil
            ringer.stop()
        case "alarm_snooze":
            reply["was_ringing"] = ringer.ringing != nil
            snooze(minutes: msg["minutes"] as? Double ?? 9)
        case "quit_all":
            log("quit requested by agent")
            conn.send(reply)
            agent.terminate()
            q.asyncAfter(deadline: .now() + 0.5) { exit(0) }
            return
        default:
            reply["ok"] = false
            reply["error"] = "unknown message type '\(type)'"
        }
        conn.send(reply)
    }
}

let coordinator = Coordinator()
coordinator.start(showAgent: !daemonMode)

signal(SIGTERM, SIG_IGN)
let term = DispatchSource.makeSignalSource(signal: SIGTERM, queue: coordinator.q)
term.setEventHandler {
    log("alfredd stopping")
    coordinator.mic.stop()
    coordinator.agent.terminate()
    unlink(Paths.socket)
    exit(0)
}
term.resume()

RunLoop.main.run()

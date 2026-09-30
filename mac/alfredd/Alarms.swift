// Alarms and timers live in the daemon so they ring whether or not the agent
// is loaded. One wall-clock timer is armed for the earliest one; nothing polls.
import AVFAudio
import Foundation

struct Alarm: Codable {
    var id: String
    var kind: String          // "alarm" | "timer"
    var label: String
    var hour: Int?
    var minute: Int?
    var days: [Int]           // ISO weekdays 1=Mon … 7=Sun; empty = once
    var fireAt: Double        // epoch seconds of the next ring
    var enabled: Bool

    func json() -> [String: Any] {
        var d: [String: Any] = ["id": id, "kind": kind, "label": label, "days": days,
                                "fire_at": fireAt, "enabled": enabled]
        d["fire_at_local"] = ISO8601DateFormatter.string(from: Date(timeIntervalSince1970: fireAt),
                                                         timeZone: .current,
                                                         formatOptions: [.withFullDate, .withTime, .withColonSeparatorInTime])
        if let h = hour { d["hour"] = h }
        if let m = minute { d["minute"] = m }
        return d
    }

    /// Next ring strictly after `after` for a repeating alarm.
    func nextOccurrence(after: Date) -> Date? {
        guard let h = hour, let m = minute, !days.isEmpty else { return nil }
        let cal = Calendar.current
        for offset in 0...7 {
            guard let day = cal.date(byAdding: .day, value: offset, to: after),
                  let at = cal.date(bySettingHour: h, minute: m, second: 0, of: day) else { continue }
            let iso = (cal.component(.weekday, from: at) + 5) % 7 + 1   // Sun=1 → 7, Mon=2 → 1
            if at > after && days.contains(iso) { return at }
        }
        return nil
    }
}

final class AlarmStore {
    var onFire: ((Alarm) -> Void)?
    private(set) var alarms: [Alarm] = []
    private let q: DispatchQueue
    private var timer: DispatchSourceTimer?

    init(queue: DispatchQueue) {
        self.q = queue
        if let data = try? Data(contentsOf: Paths.alarms),
           let list = try? JSONDecoder().decode([Alarm].self, from: data) {
            alarms = list
        }
    }

    private func save() {
        if let data = try? JSONEncoder().encode(alarms) { try? data.write(to: Paths.alarms, options: .atomic) }
    }

    func add(_ a: Alarm) {
        alarms.append(a)
        save()
        arm()
    }

    @discardableResult
    func remove(id: String) -> Int {
        let before = alarms.count
        if id == "all" { alarms.removeAll() } else { alarms.removeAll { $0.id == id } }
        save()
        arm()
        return before - alarms.count
    }

    func list() -> [[String: Any]] {
        alarms.filter { $0.enabled }.sorted { $0.fireAt < $1.fireAt }.map { $0.json() }
    }

    /// Arm the single timer for the earliest enabled alarm; fire anything overdue.
    func arm() {
        timer?.cancel()
        timer = nil
        let now = Date().timeIntervalSince1970
        var due: [Alarm] = []
        for i in alarms.indices where alarms[i].enabled && alarms[i].fireAt <= now + 0.5 {
            // Missed by more than 10 minutes (Mac was asleep): skip the ring, keep the schedule.
            if now - alarms[i].fireAt < 600 { due.append(alarms[i]) }
            if let next = alarms[i].nextOccurrence(after: Date()) {
                alarms[i].fireAt = next.timeIntervalSince1970
            } else {
                alarms[i].enabled = false
            }
        }
        alarms.removeAll { !$0.enabled }
        if !due.isEmpty { save() }
        for a in due { onFire?(a) }

        guard let next = alarms.filter({ $0.enabled }).map({ $0.fireAt }).min() else { return }
        let t = DispatchSource.makeTimerSource(queue: q)
        t.schedule(wallDeadline: .now() + max(0.05, next - Date().timeIntervalSince1970), leeway: .milliseconds(200))
        t.setEventHandler { [weak self] in self?.arm() }
        t.resume()
        timer = t
    }
}

final class Ringer {
    private(set) var ringing: Alarm?
    var onStateChange: (() -> Void)?
    private var player: AVAudioPlayer?
    private var autoStop: DispatchWorkItem?
    private var savedVolume: String?
    private let q: DispatchQueue

    init(queue: DispatchQueue) { self.q = queue }

    private static let tones = "/System/Library/PrivateFrameworks/ToneLibrary.framework/Versions/A/Resources/Ringtones/"

    func ring(_ alarm: Alarm) {
        stop(silent: true)
        ringing = alarm
        let file = alarm.kind == "timer" ? "Radial-EncoreInfinitum.m4r" : "Radar.m4r"
        var url = URL(fileURLWithPath: Ringer.tones + file)
        if !FileManager.default.fileExists(atPath: url.path) { url = URL(fileURLWithPath: "/System/Library/Sounds/Glass.aiff") }

        // An alarm nobody can hear is not an alarm: unmute and lift quiet volume, restore after.
        let settings = osascript("get volume settings")
        savedVolume = settings
        if settings.contains("output muted:true") || volumeLevel(settings) < 45 {
            osascript("set volume without output muted\nset volume output volume \(max(volumeLevel(settings), 50))")
        }
        do {
            let p = try AVAudioPlayer(contentsOf: url)
            p.numberOfLoops = -1
            p.play()
            player = p
        } catch {
            log("alarm: could not play \(url.path): \(error)")
        }
        let title = alarm.kind == "timer" ? "Timer done" : "Alarm"
        let body = alarm.label.isEmpty ? "Say \u{201C}stop\u{201D} or \u{201C}snooze\u{201D}." : alarm.label
        osascript("display notification \(appleScriptString(body)) with title \(appleScriptString("ALFRED — " + title))", wait: false)
        log("alarm: ringing \(alarm.kind) '\(alarm.label)'")
        let work = DispatchWorkItem { [weak self] in self?.stop(silent: false) }
        autoStop = work
        q.asyncAfter(deadline: .now() + (alarm.kind == "timer" ? 45 : 90), execute: work)
        onStateChange?()
    }

    private func volumeLevel(_ settings: String) -> Int {
        // "output volume:38, input volume:…, alert volume:…, output muted:false"
        guard let r = settings.range(of: "output volume:") else { return 50 }
        let digits = settings[r.upperBound...].prefix { $0.isNumber }
        return Int(digits) ?? 50
    }

    func stop(silent: Bool = false) {
        autoStop?.cancel()
        autoStop = nil
        player?.stop()
        player = nil
        if let s = savedVolume {
            let level = volumeLevel(s)
            let muted = s.contains("output muted:true")
            osascript("set volume output volume \(level)" + (muted ? "\nset volume with output muted" : ""))
            savedVolume = nil
        }
        if ringing != nil && !silent { log("alarm: stopped") }
        let was = ringing != nil
        ringing = nil
        if was { onStateChange?() }
    }
}

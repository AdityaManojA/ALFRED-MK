// Shared paths, logging and configuration for alfredd.
import Foundation

enum Paths {
    static let home = FileManager.default.homeDirectoryForCurrentUser
    static let support = home.appendingPathComponent("Library/Application Support/ALFRED", isDirectory: true)
    static let socket = support.appendingPathComponent("alfredd.sock").path
    static let lock = support.appendingPathComponent("alfredd.lock").path
    static let alarms = support.appendingPathComponent("alarms.json")
    static let config = support.appendingPathComponent("daemon.json")
    static let daemonLog = home.appendingPathComponent("Library/Logs/ALFRED-daemon.log").path
    static let agentLog = home.appendingPathComponent("Library/Logs/ALFRED.log").path
}

private let logQueue = DispatchQueue(label: "alfredd.log")
private let logStamp: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd HH:mm:ss.SSS"
    return f
}()

func log(_ message: String) {
    let line = "[\(logStamp.string(from: Date()))] \(message)\n"
    logQueue.async {
        let path = Paths.daemonLog
        if let attrs = try? FileManager.default.attributesOfItem(atPath: path),
           let size = attrs[.size] as? Int, size > 1_000_000 {
            try? FileManager.default.removeItem(atPath: path + ".1")
            try? FileManager.default.moveItem(atPath: path, toPath: path + ".1")
        }
        if !FileManager.default.fileExists(atPath: path) {
            FileManager.default.createFile(atPath: path, contents: nil)
        }
        if let h = FileHandle(forWritingAtPath: path) {
            h.seekToEndOfFile()
            h.write(line.data(using: .utf8)!)
            try? h.close()
        }
    }
}

/// daemon.json — written by mac/build.sh, editable by hand.
struct DaemonConfig: Codable {
    var repo: String
    var python: String
    /// Extra wake words on top of "alfred" and the configured assistant name.
    var wakeWords: [String]?
    /// BCP-47 locale for on-device recognition; falls back to en-US.
    var locale: String?
    /// false = "Hey Alfred" listening paused (alarms still ring).
    var listening: Bool?
    /// Multiplier over the adaptive noise floor that counts as speech.
    var vadRatio: Double?
    /// Extra multiplier while the Mac itself is playing audio (its speakers leak into the mic).
    var outputRatio: Double?
    /// Absolute RMS below which nothing counts as speech.
    var minLevel: Double?
    /// Log onsets and transcripts (for tuning; transcripts stay in the local log only).
    var debug: Bool?

    static func load() -> DaemonConfig {
        if let data = try? Data(contentsOf: Paths.config),
           let cfg = try? JSONDecoder().decode(DaemonConfig.self, from: data) {
            return cfg
        }
        // Only reached if mac/build.sh (which writes daemon.json) was never run.
        let env = ProcessInfo.processInfo.environment
        return DaemonConfig(repo: env["ALFRED_REPO"] ?? Paths.home.appendingPathComponent("ALFRED-MK-V").path,
                            python: env["ALFRED_PYTHON"] ?? "/usr/bin/python3",
                            wakeWords: nil, locale: nil, listening: true, vadRatio: nil,
                            outputRatio: nil, minLevel: nil, debug: nil)
    }

    func save() {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let data = try? enc.encode(self) { try? data.write(to: Paths.config, options: .atomic) }
    }

    /// The assistant name the user chose in ALFRED's setup (config/api_keys.json).
    var assistantName: String? {
        let url = URL(fileURLWithPath: repo).appendingPathComponent("config/api_keys.json")
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let name = obj["assistant_name"] as? String else { return nil }
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

/// Run a short AppleScript through osascript (volume handling, fallback notifications).
@discardableResult
func osascript(_ script: String, wait: Bool = true) -> String {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    p.arguments = ["-e", script]
    let out = Pipe()
    p.standardOutput = wait ? out : FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice
    do { try p.run() } catch { return "" }
    if !wait { return "" }
    p.waitUntilExit()
    let data = out.fileHandleForReading.readDataToEndOfFile()
    return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
}

func appleScriptString(_ s: String) -> String {
    "\"" + s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"") + "\""
}

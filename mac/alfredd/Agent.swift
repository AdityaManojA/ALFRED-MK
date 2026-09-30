// Spawns and tracks the Python agent (main.py).
//
// The agent is a child of this process, so macOS attributes its privacy
// permissions (microphone, Calendar, Automation, Accessibility…) to ALFRED.app.
import Foundation

final class AgentManager {
    enum State: String { case none, starting, active, dormant }

    var onStateChange: (() -> Void)?
    private(set) var state: State = .none
    private(set) var conn: Conn?
    private var proc: Process?
    private var outbox: [[String: Any]] = []
    private var startWatchdog: DispatchWorkItem?
    private let q: DispatchQueue
    private let config: () -> DaemonConfig

    init(queue: DispatchQueue, config: @escaping () -> DaemonConfig) {
        self.q = queue
        self.config = config
    }

    var isRunning: Bool { (proc?.isRunning ?? false) || conn != nil }

    func setState(_ s: State) {
        guard s != state else { return }
        state = s
        log("agent: \(s.rawValue)")
        if s == .starting {
            // If the agent never reports in, do not leave the wake word deaf.
            startWatchdog?.cancel()
            let work = DispatchWorkItem { [weak self] in
                guard let self = self, self.state == .starting else { return }
                log("agent: did not become active within 90 s")
                self.setState(self.isRunning ? .dormant : .none)
            }
            startWatchdog = work
            q.asyncAfter(deadline: .now() + 90, execute: work)
        } else {
            startWatchdog?.cancel()
        }
        onStateChange?()
    }

    func ensureRunning(reason: String) {
        if isRunning { return }
        let cfg = config()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: cfg.python)
        p.arguments = ["-u", "main.py"]
        p.currentDirectoryURL = URL(fileURLWithPath: cfg.repo)
        var env = ProcessInfo.processInfo.environment
        let pyBin = (cfg.python as NSString).deletingLastPathComponent
        env["PATH"] = "\(pyBin):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        env["ALFRED_DAEMON_SOCK"] = Paths.socket
        env["ALFRED_LAUNCH_REASON"] = reason
        env["PYTHONUNBUFFERED"] = "1"
        p.environment = env

        rotate(Paths.agentLog, limit: 5_000_000)
        let fd = open(Paths.agentLog, O_WRONLY | O_CREAT | O_APPEND, 0o644)
        if fd >= 0 {
            let h = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
            p.standardOutput = h
            p.standardError = h
        }
        p.terminationHandler = { [weak self] proc in
            self?.q.async { self?.terminated(proc) }
        }
        do {
            try p.run()
            proc = p
            log("agent: launched pid \(p.processIdentifier) (\(reason))")
            setState(.starting)
        } catch {
            log("agent: launch failed: \(error)")
        }
    }

    private func rotate(_ path: String, limit: Int) {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: path),
              let size = attrs[.size] as? Int, size > limit else { return }
        try? FileManager.default.removeItem(atPath: path + ".1")
        try? FileManager.default.moveItem(atPath: path, toPath: path + ".1")
    }

    private func terminated(_ p: Process) {
        guard p === proc else { return }
        log("agent: exited (status \(p.terminationStatus))")
        proc = nil
        if conn == nil { outbox.removeAll(); setState(.none) }
    }

    /// Queue for the agent; delivered as soon as it says hello.
    func send(_ msg: [String: Any]) {
        if let c = conn { c.send(msg) } else { outbox.append(msg) }
    }

    func attach(_ c: Conn) {
        c.isAgent = true
        conn = c
        for m in outbox { c.send(m) }
        outbox.removeAll()
    }

    func detach(_ c: Conn) {
        guard c === conn else { return }
        conn = nil
        if !(proc?.isRunning ?? false) { proc = nil; setState(.none) } else { setState(.dormant) }
    }

    func terminate() {
        proc?.terminate()
    }
}

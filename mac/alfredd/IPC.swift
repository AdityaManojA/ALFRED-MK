// Newline-delimited JSON over a user-only UNIX socket.
// The Python agent is the one long-lived client; a second ALFRED launch (or
// mac/alfredctl) connects briefly to say "show" or inject a command.
import Foundation

final class Conn {
    let fd: Int32
    var buffer = Data()
    var source: DispatchSourceRead?
    var isAgent = false

    init(fd: Int32) { self.fd = fd }

    func send(_ obj: [String: Any]) {
        guard var data = try? JSONSerialization.data(withJSONObject: obj) else { return }
        data.append(0x0A)
        data.withUnsafeBytes { raw in
            var off = 0
            while off < raw.count {
                let n = write(fd, raw.baseAddress!.advanced(by: off), raw.count - off)
                if n <= 0 { break }
                off += n
            }
        }
    }
}

final class IPCServer {
    var onMessage: ((Conn, [String: Any]) -> Void)?
    var onClose: ((Conn) -> Void)?
    private let q: DispatchQueue
    private var listenFD: Int32 = -1
    private var acceptSource: DispatchSourceRead?
    private var conns: [Int32: Conn] = [:]

    init(queue: DispatchQueue) { self.q = queue }

    private static func address(_ path: String) -> sockaddr_un {
        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        let bytes = Array(path.utf8)
        withUnsafeMutableBytes(of: &addr.sun_path) { dst in
            for (i, b) in bytes.prefix(dst.count - 1).enumerated() { dst[i] = b }
        }
        return addr
    }

    func start(path: String) -> Bool {
        unlink(path)
        listenFD = socket(AF_UNIX, SOCK_STREAM, 0)
        guard listenFD >= 0 else { return false }
        var addr = IPCServer.address(path)
        let ok = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                bind(listenFD, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) == 0
            }
        }
        guard ok else { log("ipc: bind failed errno \(errno)"); return false }
        chmod(path, 0o600)
        guard listen(listenFD, 8) == 0 else { return false }
        let src = DispatchSource.makeReadSource(fileDescriptor: listenFD, queue: q)
        src.setEventHandler { [weak self] in self?.accept() }
        src.resume()
        acceptSource = src
        return true
    }

    private func accept() {
        let fd = Darwin.accept(listenFD, nil, nil)
        guard fd >= 0 else { return }
        var on: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &on, socklen_t(MemoryLayout<Int32>.size))
        let conn = Conn(fd: fd)
        let src = DispatchSource.makeReadSource(fileDescriptor: fd, queue: q)
        src.setEventHandler { [weak self, weak conn] in
            guard let self = self, let conn = conn else { return }
            self.read(conn)
        }
        src.setCancelHandler { close(fd) }
        conn.source = src
        conns[fd] = conn
        src.resume()
    }

    private func read(_ conn: Conn) {
        var chunk = [UInt8](repeating: 0, count: 65536)
        let n = Darwin.read(conn.fd, &chunk, chunk.count)
        if n <= 0 { drop(conn); return }
        conn.buffer.append(contentsOf: chunk[0..<n])
        while let nl = conn.buffer.firstIndex(of: 0x0A) {
            let line = conn.buffer.subdata(in: conn.buffer.startIndex..<nl)
            conn.buffer.removeSubrange(conn.buffer.startIndex...nl)
            if let obj = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] {
                onMessage?(conn, obj)
            }
        }
    }

    func drop(_ conn: Conn) {
        guard conns.removeValue(forKey: conn.fd) != nil else { return }
        conn.source?.cancel()
        onClose?(conn)
    }
}

/// One-shot client used by a second launch of ALFRED.app.
func sendToRunningDaemon(_ obj: [String: Any]) -> Bool {
    let fd = socket(AF_UNIX, SOCK_STREAM, 0)
    guard fd >= 0 else { return false }
    defer { close(fd) }
    var addr = sockaddr_un()
    addr.sun_family = sa_family_t(AF_UNIX)
    let bytes = Array(Paths.socket.utf8)
    withUnsafeMutableBytes(of: &addr.sun_path) { dst in
        for (i, b) in bytes.prefix(dst.count - 1).enumerated() { dst[i] = b }
    }
    let ok = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            connect(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) == 0
        }
    }
    guard ok else { return false }
    Conn(fd: fd).send(obj)
    return true
}

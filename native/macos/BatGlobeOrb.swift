//
// BatGlobeOrb.swift
// ALFRED Mark-V — Native macOS Floating Bat Globe Orb
// Built with SwiftUI + AppKit + Metal Core Animation
//

import Cocoa
import SwiftUI
import Combine

// MARK: - IPC Model & Client

final class OrbStateModel: ObservableObject {
    @Published var stateText: String = "ALFRED // READY"
    @Published var agentState: String = "READY"
    @Published var audioRMS: Float = 0.0
    @Published var isHovered: Bool = false
    @Published var rotationAngle: Double = 0.0

    private var socketFD: Int32 = -1
    private var isConnected: Bool = false
    private let socketPath = "/tmp/alfred_orb.sock"
    private var backgroundQueue = DispatchQueue(label: "com.alfred.orb.ipc", qos: .userInteractive)

    init() {
        startIPCConnection()
    }

    func startIPCConnection() {
        backgroundQueue.async { [weak self] in
            while true {
                self?.connectSocket()
                Thread.sleep(forTimeInterval: 1.0)
            }
        }
    }

    private func connectSocket() {
        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { return }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        let pathBytes = socketPath.utf8CString
        withUnsafeMutablePointer(to: &addr.sun_path) { ptr in
            ptr.withMemoryRebound(to: CChar.self, capacity: 104) { dest in
                _ = pathBytes.withUnsafeBufferPointer { src in
                    strncpy(dest, src.baseAddress, 103)
                }
            }
        }

        let addrLen = socklen_t(MemoryLayout<sockaddr_un>.size)
        let res = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                connect(fd, sockPtr, addrLen)
            }
        }

        if res == 0 {
            self.socketFD = fd
            self.isConnected = true
            readLoop(fd: fd)
        } else {
            close(fd)
        }
    }

    private func readLoop(fd: Int32) {
        var buffer = [UInt8](repeating: 0, count: 4096)
        var stringBuffer = ""

        while isConnected {
            let bytesRead = read(fd, &buffer, buffer.count)
            if bytesRead <= 0 { break }

            if let chunk = String(bytes: buffer[0..<bytesRead], encoding: .utf8) {
                stringBuffer += chunk
                while let newlineRange = stringBuffer.range(of: "\n") {
                    let line = String(stringBuffer[..<newlineRange.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
                    stringBuffer.removeSubrange(...newlineRange.lowerBound)
                    if !line.isEmpty {
                        parseLine(line)
                    }
                }
            }
        }

        close(fd)
        socketFD = -1
        isConnected = false
    }

    private func parseLine(_ jsonString: String) {
        guard let data = jsonString.data(using: .utf8),
              let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return
        }

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            if let st = dict["state"] as? String {
                self.agentState = st.uppercased()
                switch self.agentState {
                case "LISTENING": self.stateText = "● LISTENING"
                case "THINKING":  self.stateText = "⚙ THINKING"
                case "SPEAKING":  self.stateText = "▲ SPEAKING"
                default:          self.stateText = "ALFRED // READY"
                }
            }
            if let rms = dict["rms"] as? Double {
                self.audioRMS = Float(rms)
            } else if let rms = dict["rms"] as? Float {
                self.audioRMS = rms
            }
        }
    }

    func sendAction(_ action: String, extra: [String: Any] = [:]) {
        guard isConnected, socketFD >= 0 else { return }
        var payload = extra
        payload["action"] = action
        if let data = try? JSONSerialization.data(withJSONObject: payload),
           let string = String(data: data, encoding: .utf8) {
            let line = string + "\n"
            backgroundQueue.async { [fd = self.socketFD] in
                _ = line.withCString { ptr in
                    write(fd, ptr, strlen(ptr))
                }
            }
        }
    }
}

// MARK: - 3D Wireframe Globe & Visuals

struct WireframeGlobeView: View {
    let rotationAngle: Double
    let rms: Float

    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width / 2, y: size.height / 2)
            let radius = Double(min(size.width, size.height)) * 0.44

            // 1. Ambient outer glow rings based on audio RMS
            let pulseScale = 1.0 + Double(min(1.0, max(0.0, rms * 1.8))) * 0.28
            let glowRect = CGRect(
                x: center.x - (radius * pulseScale),
                y: center.y - (radius * pulseScale),
                width: radius * 2 * pulseScale,
                height: radius * 2 * pulseScale
            )
            context.stroke(
                Circle().path(in: glowRect),
                with: .color(Color(red: 0.0, green: 0.85, blue: 1.0).opacity(0.35 + Double(rms) * 0.4)),
                lineWidth: 1.5
            )

            // 2. Latitude Circles
            let latAngles: [Double] = [-60, -40, -20, 0, 20, 40, 60]
            for lat in latAngles {
                let r = radius * cos(lat * .pi / 180.0)
                let yOffset = radius * sin(lat * .pi / 180.0)
                let tilt = 0.35 // Perspective foreshortening
                let ringRect = CGRect(
                    x: center.x - r,
                    y: center.y - yOffset * (1.0 - tilt) - (r * tilt * 0.5),
                    width: r * 2,
                    height: r * 2 * tilt
                )
                let isEquator = lat == 0
                context.stroke(
                    Ellipse().path(in: ringRect),
                    with: .color(Color(red: 0.0, green: 0.85, blue: 1.0).opacity(isEquator ? 0.75 : 0.28)),
                    lineWidth: isEquator ? 1.4 : 0.8
                )
            }

            // 3. Longitude Meridians (Rotating with perspective)
            let meridianCount = 12
            for i in 0..<meridianCount {
                let baseAngle = (Double(i) / Double(meridianCount)) * Double.pi
                let curAngle = baseAngle + rotationAngle
                let xFactor = cos(curAngle)
                let ellipseWidth = abs(radius * 2 * xFactor)
                let mRect = CGRect(
                    x: center.x - (ellipseWidth / 2),
                    y: center.y - radius,
                    width: ellipseWidth,
                    height: radius * 2
                )
                let alpha = 0.22 + 0.38 * abs(sin(curAngle))
                context.stroke(
                    Ellipse().path(in: mRect),
                    with: .color(Color(red: 0.0, green: 0.85, blue: 1.0).opacity(alpha)),
                    lineWidth: 0.9
                )
            }

            // 4. Perimeter Ticks (HUD Dial markers)
            let tickCount = 36
            for t in 0..<tickCount {
                let a = (Double(t) / Double(tickCount)) * 2 * Double.pi
                let r1 = radius + 4
                let r2 = radius + (t % 3 == 0 ? 10 : 7)
                let p1 = CGPoint(x: center.x + r1 * cos(a), y: center.y + r1 * sin(a))
                let p2 = CGPoint(x: center.x + r2 * cos(a), y: center.y + r2 * sin(a))
                var path = Path()
                path.move(to: p1)
                path.addLine(to: p2)
                context.stroke(path, with: .color(Color(red: 0.0, green: 0.85, blue: 1.0).opacity(t % 3 == 0 ? 0.6 : 0.25)), lineWidth: 1.0)
            }
        }
    }
}

// MARK: - Wayne Crest Watermark

struct WayneCrestView: View {
    var body: some View {
        Canvas { context, size in
            let w = size.width
            let h = size.height
            let cx = w / 2
            let cy = h / 2

            // Minimalist Wayne Enterprise Bat silhouette
            var path = Path()
            path.move(to: CGPoint(x: cx, y: cy - 14))
            path.addQuadCurve(to: CGPoint(x: cx - 28, y: cy - 18), control: CGPoint(x: cx - 12, y: cy - 24))
            path.addQuadCurve(to: CGPoint(x: cx - 36, y: cy - 2), control: CGPoint(x: cx - 34, y: cy - 12))
            path.addQuadCurve(to: CGPoint(x: cx - 20, y: cy + 12), control: CGPoint(x: cx - 28, y: cy + 6))
            path.addQuadCurve(to: CGPoint(x: cx, y: cy + 22), control: CGPoint(x: cx - 10, y: cy + 18))
            path.addQuadCurve(to: CGPoint(x: cx + 20, y: cy + 12), control: CGPoint(x: cx + 10, y: cy + 18))
            path.addQuadCurve(to: CGPoint(x: cx + 36, y: cy - 2), control: CGPoint(x: cx + 28, y: cy + 6))
            path.addQuadCurve(to: CGPoint(x: cx + 28, y: cy - 18), control: CGPoint(x: cx + 34, y: cy - 12))
            path.addQuadCurve(to: CGPoint(x: cx, y: cy - 14), control: CGPoint(x: cx + 12, y: cy - 24))
            path.closeSubpath()

            context.fill(path, with: .color(Color(red: 0.0, green: 0.85, blue: 1.0).opacity(0.18)))
            context.stroke(path, with: .color(Color(red: 0.0, green: 0.85, blue: 1.0).opacity(0.40)), lineWidth: 1.0)
        }
    }
}

// MARK: - Main SwiftUI Orb View

struct BatGlobeOrbView: View {
    @ObservedObject var model: OrbStateModel

    var statusColor: Color {
        switch model.agentState {
        case "LISTENING": return Color(red: 0.0, green: 1.0, blue: 0.7)
        case "THINKING":  return Color(red: 1.0, green: 0.75, blue: 0.1)
        case "SPEAKING":  return Color(red: 0.2, green: 0.9, blue: 1.0)
        default:          return Color(red: 0.0, green: 0.75, blue: 0.95).opacity(0.7)
        }
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
            let angle = time * 0.45

            ZStack {
                // 1. Ultra-thin Apple Liquid Glass Backdrop
                Circle()
                    .fill(.ultraThinMaterial)
                    .overlay(
                        Circle()
                            .strokeBorder(
                                LinearGradient(
                                    colors: [
                                        Color(red: 0.0, green: 0.85, blue: 1.0).opacity(0.8),
                                        Color(red: 0.0, green: 0.4, blue: 0.8).opacity(0.3),
                                        Color(red: 0.0, green: 0.85, blue: 1.0).opacity(0.6)
                                    ],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ),
                                lineWidth: 1.5
                            )
                    )
                    .shadow(color: Color(red: 0.0, green: 0.85, blue: 1.0).opacity(0.35), radius: 12, x: 0, y: 0)

                // 2. Wayne Crest Ambient Watermark
                WayneCrestView()
                    .frame(width: 80, height: 50)

                // 3. 3D Wireframe Globe with smooth 120Hz rotation
                WireframeGlobeView(rotationAngle: angle, rms: model.audioRMS)
                    .frame(width: 210, height: 210)

                // 4. Status Badge Pill
                VStack {
                    Spacer()
                    HStack(spacing: 5) {
                        Circle()
                            .fill(statusColor)
                            .frame(width: 6, height: 6)
                            .shadow(color: statusColor, radius: 4)
                        Text(model.stateText)
                            .font(.system(size: 9.5, weight: .bold, design: .monospaced))
                            .foregroundColor(statusColor)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(
                        Capsule()
                            .fill(Color.black.opacity(0.72))
                            .overlay(Capsule().stroke(statusColor.opacity(0.4), lineWidth: 0.8))
                    )
                    .padding(.bottom, 18)
                }

                // 5. Hover Actions (Expand & Close)
                if model.isHovered {
                    VStack {
                        HStack {
                            Button(action: {
                                performHaptic()
                                model.sendAction("close")
                                NSApp.terminate(nil)
                            }) {
                                Image(systemName: "xmark")
                                    .font(.system(size: 9, weight: .bold))
                                    .foregroundColor(.white.opacity(0.8))
                                    .frame(width: 20, height: 20)
                                    .background(Circle().fill(Color.black.opacity(0.6)))
                            }
                            .buttonStyle(.plain)

                            Spacer()

                            Button(action: {
                                performHaptic()
                                model.sendAction("expand_hud")
                            }) {
                                Image(systemName: "arrow.up.left.and.arrow.down.right")
                                    .font(.system(size: 9, weight: .bold))
                                    .foregroundColor(.cyan)
                                    .frame(width: 20, height: 20)
                                    .background(Circle().fill(Color.black.opacity(0.6)))
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 22)
                        .padding(.top, 20)

                        Spacer()
                    }
                    .transition(.opacity)
                }
            }
            .frame(width: 240, height: 240)
            .contentShape(Circle())
            .onHover { hovering in
                withAnimation(.easeInOut(duration: 0.18)) {
                    model.isHovered = hovering
                }
            }
            .onTapGesture(count: 2) {
                performHaptic()
                model.sendAction("expand_hud")
            }
            .onTapGesture(count: 1) {
                performHaptic()
                model.sendAction("tap")
            }
        }
    }

    private func performHaptic() {
        NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
    }
}

// MARK: - Native Draggable NSPanel Host

final class DraggablePanel: NSPanel {
    private var initialLocation: NSPoint = .zero

    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }

    override func mouseDown(with event: NSEvent) {
        initialLocation = event.locationInWindow
    }

    override func mouseDragged(with event: NSEvent) {
        guard let screen = self.screen ?? NSScreen.main else { return }
        let currentLocation = NSEvent.mouseLocation
        var newOrigin = NSPoint(
            x: currentLocation.x - initialLocation.x,
            y: currentLocation.y - initialLocation.y
        )

        // Clamp inside screen bounds
        let screenFrame = screen.visibleFrame
        newOrigin.x = max(screenFrame.minX, min(newOrigin.x, screenFrame.maxX - frame.width))
        newOrigin.y = max(screenFrame.minY, min(newOrigin.y, screenFrame.maxY - frame.height))

        setFrameOrigin(newOrigin)
        savePosition(newOrigin)
    }

    private func savePosition(_ pt: NSPoint) {
        let path = ("~/.alfred/bat_globe_pos.json" as NSString).expandingTildeInPath
        let dict: [String: Double] = ["x": pt.x, "y": pt.y]
        if let data = try? JSONSerialization.data(withJSONObject: dict) {
            try? data.write(to: URL(fileURLWithPath: path))
        }
    }

    func loadSavedPosition() -> NSPoint? {
        let path = ("~/.alfred/bat_globe_pos.json" as NSString).expandingTildeInPath
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Double],
              let x = dict["x"], let y = dict["y"] else {
            return nil
        }
        return NSPoint(x: x, y: y)
    }
}

// MARK: - App Delegate & Main Entry

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: DraggablePanel!
    private let model = OrbStateModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory) // Pinned floating companion, no Dock clutter

        let panel = DraggablePanel(
            contentRect: NSRect(x: 0, y: 0, width: 240, height: 240),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isMovableByWindowBackground = false

        // Position window: bottom-right or saved coordinates
        if let saved = panel.loadSavedPosition() {
            panel.setFrameOrigin(saved)
        } else if let screen = NSScreen.main {
            let sf = screen.visibleFrame
            panel.setFrameOrigin(NSPoint(x: sf.maxX - 260, y: sf.minY + 40))
        }

        let hostingView = NSHostingView(rootView: BatGlobeOrbView(model: model))
        panel.contentView = hostingView
        panel.orderFrontRegardless()
        self.window = panel
    }
}

// Main Bootstrapper
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()

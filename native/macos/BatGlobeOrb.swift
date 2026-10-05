//
// BatGlobeOrb.swift
// ALFRED Mark-V — Tactical Batcomputer Floating Orb
// Inspired by Wayne Tech, the Batmobile cockpit HUD, and Apple Intelligence
// Built with SwiftUI + AppKit + Core Animation
//

import Cocoa
import SwiftUI
import Combine

// MARK: - IPC Model & State Management

final class OrbStateModel: ObservableObject {
    @Published var stateText: String = "WAYNE TECH // READY"
    @Published var agentState: String = "READY"
    @Published var audioRMS: Float = 0.0
    @Published var smoothedRMS: Float = 0.0
    @Published var isHovered: Bool = false
    @Published var isMuted: Bool = false
    @Published var clickPulse: CGFloat = 0.0

    private var socketFD: Int32 = -1
    private var isConnected: Bool = false
    private let socketPath = "/tmp/alfred_orb.sock"
    private var backgroundQueue = DispatchQueue(label: "com.alfred.batglobe.ipc", qos: .userInteractive)
    private var cancellables = Set<AnyCancellable>()

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
                case "LISTENING":
                    self.stateText = "UPLINK // LISTENING"
                case "THINKING":
                    self.stateText = "SYNAPSE // PROCESSING"
                case "SPEAKING":
                    self.stateText = "VOCAL // TRANSMITTING"
                case "SLEEPING":
                    self.stateText = "BATCOMPUTER // STANDBY"
                default:
                    self.stateText = "WAYNE TECH // READY"
                }
            }
            if let rms = dict["rms"] as? Double {
                self.updateAudio(Float(rms))
            } else if let rms = dict["rms"] as? Float {
                self.updateAudio(rms)
            }
        }
    }

    private func updateAudio(_ raw: Float) {
        self.audioRMS = raw
        // Smooth exponential interpolation for butter-smooth visual responses
        self.smoothedRMS = self.smoothedRMS * 0.65 + raw * 0.35
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

    func triggerClickPulse() {
        withAnimation(.easeOut(duration: 0.45)) {
            self.clickPulse = 1.0
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) {
            self.clickPulse = 0.0
        }
    }
}

// MARK: - Tactical Colors

// MARK: - Tactical & Apple Intelligence Spectral Colors

struct BatTheme {
    // Batman x Wayne Tech tones
    static let darkVoid       = Color(red: 0.03, green: 0.05, blue: 0.08)
    static let stealthBezel   = Color(red: 0.08, green: 0.12, blue: 0.16)
    static let wayneCyan      = Color(red: 0.0, green: 0.88, blue: 1.0)
    static let emeraldGlow    = Color(red: 0.0, green: 1.0, blue: 0.65)
    static let amberAlert    = Color(red: 1.0, green: 0.72, blue: 0.1)
    static let crimsonKill   = Color(red: 1.0, green: 0.22, blue: 0.3)

    // Siri AI / Apple Intelligence Liquid Glass Spectral Accents
    static let siriViolet    = Color(red: 0.68, green: 0.32, blue: 1.0)
    static let siriMagenta   = Color(red: 0.96, green: 0.26, blue: 0.68)
    static let siriTeal      = Color(red: 0.08, green: 0.92, blue: 0.84)
    static let siriCobalt    = Color(red: 0.16, green: 0.42, blue: 0.96)
    static let liquidIce     = Color(red: 0.90, green: 0.97, blue: 1.0)
}

// MARK: - Authentic Wayne Bat Insignia

struct BatInsigniaShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let w = rect.width
        let h = rect.height
        let cx = rect.midX
        let cy = rect.midY

        // Razor-sharp modern Bat silhouette
        let scaleX = w / 100.0
        let scaleY = h / 60.0

        p.move(to: CGPoint(x: cx, y: cy - 14 * scaleY))
        // Left Ear & Wing Peak
        p.addLine(to: CGPoint(x: cx - 4 * scaleX, y: cy - 22 * scaleY))
        p.addLine(to: CGPoint(x: cx - 8 * scaleX, y: cy - 14 * scaleY))
        p.addQuadCurve(to: CGPoint(x: cx - 44 * scaleX, y: cy - 16 * scaleY),
                       control: CGPoint(x: cx - 22 * scaleX, y: cy - 26 * scaleY))
        // Left Outer Wing Tip
        p.addQuadCurve(to: CGPoint(x: cx - 48 * scaleX, y: cy + 4 * scaleY),
                       control: CGPoint(x: cx - 50 * scaleX, y: cy - 6 * scaleY))
        // Left Wing Underside Scallops
        p.addQuadCurve(to: CGPoint(x: cx - 28 * scaleX, y: cy + 8 * scaleY),
                       control: CGPoint(x: cx - 38 * scaleX, y: cy + 18 * scaleY))
        p.addQuadCurve(to: CGPoint(x: cx - 12 * scaleX, y: cy + 16 * scaleY),
                       control: CGPoint(x: cx - 20 * scaleX, y: cy + 24 * scaleY))
        // Tail Point
        p.addQuadCurve(to: CGPoint(x: cx, y: cy + 26 * scaleY),
                       control: CGPoint(x: cx - 4 * scaleX, y: cy + 22 * scaleY))
        // Right Wing Underside Scallops
        p.addQuadCurve(to: CGPoint(x: cx + 12 * scaleX, y: cy + 16 * scaleY),
                       control: CGPoint(x: cx + 4 * scaleX, y: cy + 22 * scaleY))
        p.addQuadCurve(to: CGPoint(x: cx + 28 * scaleX, y: cy + 8 * scaleY),
                       control: CGPoint(x: cx + 20 * scaleX, y: cy + 24 * scaleY))
        p.addQuadCurve(to: CGPoint(x: cx + 48 * scaleX, y: cy + 4 * scaleY),
                       control: CGPoint(x: cx + 38 * scaleX, y: cy + 18 * scaleY))
        // Right Outer Wing Tip
        p.addQuadCurve(to: CGPoint(x: cx + 44 * scaleX, y: cy - 16 * scaleY),
                       control: CGPoint(x: cx + 50 * scaleX, y: cy - 6 * scaleY))
        // Right Ear & Wing Peak
        p.addQuadCurve(to: CGPoint(x: cx + 8 * scaleX, y: cy - 14 * scaleY),
                       control: CGPoint(x: cx + 22 * scaleX, y: cy - 26 * scaleY))
        p.addLine(to: CGPoint(x: cx + 4 * scaleX, y: cy - 22 * scaleY))
        p.closeSubpath()

        return p
    }
}

// MARK: - Batcomputer 3D Multi-Ring Gyroscope & Waveforms

struct BatcomputerGyroView: View {
    let rotationAngle: Double
    let rms: Float
    let stateColor: Color

    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width / 2, y: size.height / 2)
            let maxRadius = Double(min(size.width, size.height)) * 0.44

            // ── 1. Tactical Azimuth Bezel & Radar Ring ────────────────────
            let bezelRect = CGRect(x: center.x - maxRadius, y: center.y - maxRadius, width: maxRadius * 2, height: maxRadius * 2)
            context.stroke(
                Circle().path(in: bezelRect),
                with: .color(stateColor.opacity(0.30)),
                lineWidth: 1.2
            )

            // Compass Cardinal Ticks (0°, 90°, 180°, 270°)
            for i in 0..<4 {
                let ang = Double(i) * Double.pi / 2.0
                let pOuter = CGPoint(x: center.x + (maxRadius + 5) * cos(ang), y: center.y + (maxRadius + 5) * sin(ang))
                let pInner = CGPoint(x: center.x + (maxRadius - 5) * cos(ang), y: center.y + (maxRadius - 5) * sin(ang))
                var mark = Path()
                mark.move(to: pOuter)
                mark.addLine(to: pInner)
                context.stroke(mark, with: .color(stateColor.opacity(0.75)), lineWidth: 1.8)
            }

            // Radar Scan Line Sweep
            let sweepAngle = rotationAngle * 1.4
            let sweepEnd = CGPoint(x: center.x + maxRadius * cos(sweepAngle), y: center.y + maxRadius * sin(sweepAngle))
            var sweepPath = Path()
            sweepPath.move(to: center)
            sweepPath.addLine(to: sweepEnd)
            context.stroke(sweepPath, with: .color(stateColor.opacity(0.24)), lineWidth: 1.0)

            // ── 2. Concentric Equalizer Arc Pins (Dynamic to voice) ──────
            let pinCount = 36
            let eqRadius = maxRadius * 0.88
            let energy = Double(min(1.0, max(0.0, rms * 2.2)))

            for i in 0..<pinCount {
                let a = (Double(i) / Double(pinCount)) * 2 * Double.pi
                let waveMod = abs(sin(a * 4 + rotationAngle * 3)) * energy
                let pinLength = 2.5 + waveMod * 15.0
                let p1 = CGPoint(x: center.x + (eqRadius - pinLength) * cos(a), y: center.y + (eqRadius - pinLength) * sin(a))
                let p2 = CGPoint(x: center.x + eqRadius * cos(a), y: center.y + eqRadius * sin(a))
                var pin = Path()
                pin.move(to: p1)
                pin.addLine(to: p2)
                context.stroke(pin, with: .color(stateColor.opacity(0.30 + waveMod * 0.55)), lineWidth: 1.3)
            }

            // ── 3. 3D Wireframe Spherical Globe ──────────────────────────
            let globeRadius = maxRadius * 0.68
            // Latitude Rings
            let latitudes: [Double] = [-50, -25, 0, 25, 50]
            for lat in latitudes {
                let r = globeRadius * cos(lat * .pi / 180.0)
                let yOff = globeRadius * sin(lat * .pi / 180.0) * 0.38
                let ringRect = CGRect(x: center.x - r, y: center.y - yOff - (r * 0.18), width: r * 2, height: r * 0.36)
                let isEquator = lat == 0
                context.stroke(
                    Ellipse().path(in: ringRect),
                    with: .color(stateColor.opacity(isEquator ? 0.65 : 0.18)),
                    lineWidth: isEquator ? 1.3 : 0.75
                )
            }

            // Longitude Meridians in 3D Motion
            let meridians = 10
            for i in 0..<meridians {
                let baseAngle = (Double(i) / Double(meridians)) * Double.pi
                let curAngle = baseAngle + rotationAngle * 0.6
                let xFactor = cos(curAngle)
                let width = abs(globeRadius * 2 * xFactor)
                let mRect = CGRect(x: center.x - (width / 2), y: center.y - globeRadius, width: width, height: globeRadius * 2)
                let alpha = 0.12 + 0.32 * abs(sin(curAngle))
                context.stroke(
                    Ellipse().path(in: mRect),
                    with: .color(stateColor.opacity(alpha)),
                    lineWidth: 0.85
                )
            }
        }
    }
}

// MARK: - Main Batcomputer Orb View (Siri AI / Apple Intelligence Liquid Glass)

struct BatGlobeOrbView: View {
    @ObservedObject var model: OrbStateModel

    var activeColor: Color {
        if model.isMuted {
            return BatTheme.crimsonKill
        }
        switch model.agentState {
        case "LISTENING": return BatTheme.emeraldGlow
        case "THINKING":  return BatTheme.amberAlert
        case "SPEAKING":  return BatTheme.wayneCyan
        case "SLEEPING":  return Color.gray.opacity(0.5)
        default:          return BatTheme.wayneCyan
        }
    }

    /// Apple Intelligence / Siri AI flowing chromatic spectrum
    var liquidColors: [Color] {
        if model.isMuted {
            return [
                BatTheme.crimsonKill,
                Color.orange,
                BatTheme.crimsonKill.opacity(0.85),
                BatTheme.liquidIce,
                BatTheme.crimsonKill
            ]
        }
        switch model.agentState {
        case "LISTENING":
            return [
                BatTheme.emeraldGlow,
                BatTheme.siriTeal,
                BatTheme.liquidIce,
                BatTheme.emeraldGlow,
                BatTheme.siriTeal
            ]
        case "THINKING":
            return [
                BatTheme.amberAlert,
                BatTheme.siriMagenta,
                BatTheme.siriViolet,
                BatTheme.amberAlert,
                BatTheme.liquidIce
            ]
        case "SPEAKING":
            return [
                BatTheme.siriTeal,
                BatTheme.wayneCyan,
                BatTheme.siriCobalt,
                BatTheme.liquidIce,
                BatTheme.siriTeal
            ]
        case "SLEEPING":
            return [
                Color.gray.opacity(0.4),
                Color.blue.opacity(0.3),
                Color.white.opacity(0.25),
                Color.gray.opacity(0.4)
            ]
        default: // READY / STANDBY
            return [
                BatTheme.siriTeal,
                BatTheme.wayneCyan,
                BatTheme.siriCobalt,
                BatTheme.siriViolet,
                BatTheme.siriTeal
            ]
        }
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
            let angle = time * 0.65
            let pulseEnergy = 1.0 + CGFloat(model.smoothedRMS * 0.45)
            let orbSize: CGFloat = 202

            ZStack {
                // ── LAYER 1: Siri AI Atmospheric Liquid Caustic Outer Bloom ─
                // Dissolves smoothly into macOS desktop wallpaper
                Circle()
                    .strokeBorder(
                        AngularGradient(
                            colors: liquidColors,
                            center: .center,
                            angle: .radians(angle)
                        ),
                        lineWidth: 9.0 + CGFloat(model.smoothedRMS * 14.0)
                    )
                    .frame(width: orbSize, height: orbSize)
                    .blur(radius: 12.0 + CGFloat(model.smoothedRMS * 8.0))
                    .opacity(0.55 + Double(model.smoothedRMS * 0.35))

                // ── LAYER 2: UltraThin Frosted Liquid Glass Core ─────────────
                // Live macOS backdrop blur ensures true background blending
                Circle()
                    .fill(.ultraThinMaterial)
                    .frame(width: orbSize, height: orbSize)
                    .overlay(
                        // Subtle refractive tint to preserve contrast without blocking background
                        Circle()
                            .fill(
                                RadialGradient(
                                    colors: [
                                        Color.white.opacity(0.04),
                                        Color.black.opacity(0.16),
                                        Color.black.opacity(0.40)
                                    ],
                                    center: .center,
                                    startRadius: 15,
                                    endRadius: orbSize / 2
                                )
                            )
                    )

                // ── LAYER 3: 3D Spherical Specular Glass Refraction ─────────
                // Gives the illusion of a volumetric convex liquid lens
                Circle()
                    .fill(
                        EllipticalGradient(
                            colors: [
                                Color.white.opacity(0.24),
                                Color.white.opacity(0.06),
                                Color.clear
                            ],
                            center: .init(x: 0.32, y: 0.22),
                            startRadiusFraction: 0.0,
                            endRadiusFraction: 0.44
                        )
                    )
                    .frame(width: orbSize, height: orbSize)

                // ── LAYER 4: Chromatic Liquid Rim Ribbons ───────────────────
                // Mid flowing caustic ribbon
                Circle()
                    .strokeBorder(
                        AngularGradient(
                            colors: liquidColors,
                            center: .center,
                            angle: .radians(-angle * 1.25)
                        ),
                        lineWidth: 2.4 + CGFloat(model.smoothedRMS * 2.5)
                    )
                    .frame(width: orbSize, height: orbSize)
                    .blur(radius: 2.2)
                    .opacity(0.85)

                // Crisp iridescent hairline rim
                Circle()
                    .strokeBorder(
                        AngularGradient(
                            colors: liquidColors,
                            center: .center,
                            angle: .radians(angle)
                        ),
                        lineWidth: 1.2
                    )
                    .frame(width: orbSize, height: orbSize)
                    .opacity(0.95)

                // Specular Bevel Arc Highlight (top-left glass rim)
                Circle()
                    .strokeBorder(
                        LinearGradient(
                            colors: [
                                Color.white.opacity(0.65),
                                Color.white.opacity(0.12),
                                Color.clear,
                                Color.white.opacity(0.18)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1.1
                    )
                    .frame(width: orbSize, height: orbSize)

                // ── LAYER 5: Click Shockwave Ripple ────────────────────────
                if model.clickPulse > 0 {
                    Circle()
                        .stroke(activeColor.opacity(Double(1.0 - model.clickPulse)), lineWidth: 2.8)
                        .scaleEffect(0.55 + model.clickPulse * 0.75)
                        .frame(width: orbSize, height: orbSize)
                }

                // ── LAYER 6: Batcomputer 3D Gyroscope Suspended in Glass ────
                BatcomputerGyroView(rotationAngle: angle, rms: model.smoothedRMS, stateColor: activeColor)
                    .frame(width: orbSize * 0.94, height: orbSize * 0.94)

                // ── LAYER 7: Centerpiece Wayne Bat Insignia Hologram ────────
                ZStack {
                    // Ambient Neon Back-Glow
                    BatInsigniaShape()
                        .fill(activeColor.opacity(0.30 + Double(model.smoothedRMS) * 0.50))
                        .blur(radius: 7 + CGFloat(model.smoothedRMS * 10))

                    // Translucent Frosted Glass Bat Core with Sharp Edge
                    BatInsigniaShape()
                        .stroke(activeColor.opacity(0.95), lineWidth: 1.5)
                        .background(
                            BatInsigniaShape()
                                .fill(Color.black.opacity(0.32))
                        )
                }
                .frame(width: 76, height: 44)
                .scaleEffect(pulseEnergy)
                .animation(.spring(response: 0.25, dampingFraction: 0.65), value: pulseEnergy)

                // ── LAYER 8: Frosted Status HUD Pill (Siri AI Capsule) ─────
                VStack {
                    Spacer()
                    HStack(spacing: 5) {
                        Circle()
                            .fill(activeColor)
                            .frame(width: 5.0, height: 5.0)
                            .shadow(color: activeColor, radius: 4)
                        Text(model.stateText)
                            .font(.system(size: 8.4, weight: .bold, design: .monospaced))
                            .foregroundColor(activeColor)
                    }
                    .padding(.horizontal, 9)
                    .padding(.vertical, 3.5)
                    .background(
                        Capsule()
                            .fill(.ultraThinMaterial)
                            .overlay(
                                Capsule()
                                    .stroke(
                                        LinearGradient(
                                            colors: [activeColor.opacity(0.55), Color.white.opacity(0.20)],
                                            startPoint: .topLeading,
                                            endPoint: .bottomTrailing
                                        ),
                                        lineWidth: 0.8
                                    )
                            )
                    )
                    .padding(.bottom, 20)
                }
                .frame(width: orbSize, height: orbSize)

                // ── LAYER 9: Frosted Glass Floating Action Controls ─────────
                if model.isHovered {
                    VStack {
                        HStack {
                            // Mic Mute / Unmute Button
                            Button(action: {
                                performHaptic()
                                model.isMuted.toggle()
                                model.sendAction("toggle_mute")
                            }) {
                                Image(systemName: model.isMuted ? "mic.slash.fill" : "mic.fill")
                                    .font(.system(size: 9.2, weight: .bold))
                                    .foregroundColor(model.isMuted ? .red : activeColor)
                                    .frame(width: 22, height: 22)
                                    .background(Circle().fill(.ultraThinMaterial))
                                    .overlay(Circle().stroke(activeColor.opacity(0.4), lineWidth: 0.8))
                            }
                            .buttonStyle(.plain)

                            Spacer()

                            // Full Batcomputer HUD Expand
                            Button(action: {
                                performHaptic()
                                model.triggerClickPulse()
                                model.sendAction("expand_hud")
                            }) {
                                Image(systemName: "arrow.up.left.and.arrow.down.right")
                                    .font(.system(size: 9.2, weight: .bold))
                                    .foregroundColor(activeColor)
                                    .frame(width: 22, height: 22)
                                    .background(Circle().fill(.ultraThinMaterial))
                                    .overlay(Circle().stroke(activeColor.opacity(0.4), lineWidth: 0.8))
                            }
                            .buttonStyle(.plain)

                            // Close / Sleep
                            Button(action: {
                                performHaptic()
                                model.sendAction("close")
                                NSApp.terminate(nil)
                            }) {
                                Image(systemName: "xmark")
                                    .font(.system(size: 9.2, weight: .bold))
                                    .foregroundColor(.white.opacity(0.85))
                                    .frame(width: 22, height: 22)
                                    .background(Circle().fill(.ultraThinMaterial))
                                    .overlay(Circle().stroke(Color.white.opacity(0.3), lineWidth: 0.8))
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 24)
                        .padding(.top, 20)

                        Spacer()
                    }
                    .frame(width: orbSize, height: orbSize)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
                }
            }
            .frame(width: 230, height: 230)
            .contentShape(Circle())
            .scaleEffect(model.isHovered ? 1.03 : 1.0)
            .animation(.easeOut(duration: 0.18), value: model.isHovered)
            .onHover { hovering in
                model.isHovered = hovering
            }
            .onTapGesture(count: 2) {
                performHaptic()
                model.triggerClickPulse()
                model.sendAction("expand_hud")
            }
            .onTapGesture(count: 1) {
                performHaptic()
                model.triggerClickPulse()
                model.sendAction("tap")
            }
        }
    }

    private func performHaptic() {
        NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
    }
}

// MARK: - Native Draggable NSPanel Host with Magnetic Edge Snapping

final class DraggablePanel: NSPanel {
    private var initialLocation: NSPoint = .zero
    var model: OrbStateModel?

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

        let screenFrame = screen.visibleFrame
        // Magnetic Edge Snapping (snap when within 30px of display borders)
        let snapDist: CGFloat = 30
        if abs(newOrigin.x - screenFrame.minX) < snapDist {
            newOrigin.x = screenFrame.minX + 8
        } else if abs((newOrigin.x + frame.width) - screenFrame.maxX) < snapDist {
            newOrigin.x = screenFrame.maxX - frame.width - 8
        }

        if abs(newOrigin.y - screenFrame.minY) < snapDist {
            newOrigin.y = screenFrame.minY + 8
        } else if abs((newOrigin.y + frame.height) - screenFrame.maxY) < snapDist {
            newOrigin.y = screenFrame.maxY - frame.height - 8
        }

        // Clamp to prevent moving completely offscreen
        newOrigin.x = max(screenFrame.minX, min(newOrigin.x, screenFrame.maxX - frame.width))
        newOrigin.y = max(screenFrame.minY, min(newOrigin.y, screenFrame.maxY - frame.height))

        setFrameOrigin(newOrigin)
        savePosition(newOrigin)
    }

    override func rightMouseDown(with event: NSEvent) {
        let menu = NSMenu(title: "Batcomputer Orb")

        let listenItem = NSMenuItem(title: "🎙 Talk to ALFRED", action: #selector(onMenuTalk), keyEquivalent: "")
        let muteItem = NSMenuItem(title: (model?.isMuted ?? false) ? "🔊 Unmute Microphone" : "🔇 Mute Microphone", action: #selector(onMenuToggleMute), keyEquivalent: "")
        let expandItem = NSMenuItem(title: "💻 Expand Batcomputer HUD", action: #selector(onMenuExpand), keyEquivalent: "")
        let centerItem = NSMenuItem(title: "📍 Reset Position", action: #selector(onMenuCenter), keyEquivalent: "")
        let quitItem = NSMenuItem(title: "✕ Quit ALFRED", action: #selector(onMenuQuit), keyEquivalent: "q")

        for item in [listenItem, muteItem, expandItem, centerItem] {
            item.target = self
            menu.addItem(item)
        }
        menu.addItem(NSMenuItem.separator())
        quitItem.target = self
        menu.addItem(quitItem)

        NSMenu.popUpContextMenu(menu, with: event, for: self.contentView!)
    }

    @objc private func onMenuTalk() {
        model?.sendAction("tap")
    }

    @objc private func onMenuToggleMute() {
        model?.isMuted.toggle()
        model?.sendAction("toggle_mute")
    }

    @objc private func onMenuExpand() {
        model?.sendAction("expand_hud")
    }

    @objc private func onMenuCenter() {
        if let screen = NSScreen.main {
            let sf = screen.visibleFrame
            setFrameOrigin(NSPoint(x: sf.maxX - 260, y: sf.minY + 40))
            savePosition(frame.origin)
        }
    }

    @objc private func onMenuQuit() {
        model?.sendAction("close")
        NSApp.terminate(nil)
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
        NSApp.setActivationPolicy(.accessory) // Pinned floating accessory, no Dock clutter

        let panel = DraggablePanel(
            contentRect: NSRect(x: 0, y: 0, width: 230, height: 230),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        panel.model = model
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isMovableByWindowBackground = false

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

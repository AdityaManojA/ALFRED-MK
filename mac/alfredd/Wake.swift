// Two-stage wake detection.
//
// Stage 1 (always on, ~free): an energy VAD over the 85 ms HAL chunks with an
// adaptive noise floor. Silence costs one RMS per chunk and a copy into the
// pre-roll ring.
// Stage 2 (only while someone is talking): Apple's on-device speech recognizer
// is fed the pre-roll plus live audio. If the first few words contain the wake
// word, we switch to capturing the command that follows until the speaker
// pauses, then hand the text to the agent. Ordinary conversation is abandoned
// after a handful of words, so a busy room does not keep the recognizer busy.
import AVFAudio
import Foundation
import Speech

final class WakeEngine {
    enum Mode { case idle, probing, finishingProbe, command, finishingCommand }

    var onWake: (() -> Void)?
    /// Transcript after the wake word, plus the whole utterance as 16 kHz PCM
    /// (the agent streams the audio to Gemini, which transcribes far better).
    var onCommand: ((String, [Int16]) -> Void)?
    /// Every transcript while `transcribeAll` is set (alarm ringing: "stop", "snooze").
    var onUtterance: ((String) -> Void)?
    var transcribeAll = false
    /// The Mac is playing audio: most of what the mic hears is our own speakers.
    var outputActive = false
    var debug = false

    private(set) var mode: Mode = .idle
    private let q: DispatchQueue
    private var recognizer: SFSpeechRecognizer?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var format: AVAudioFormat?
    private var sessionID = 0
    private var sessionStart = Date()
    private var lastText = ""
    private var strongWords: Set<String> = []
    private let weakWords: Set<String> = ["albert", "alfie", "elford", "alfa", "alford's", "alfredo's"]
    private let prefixes: Set<String> = ["hey", "hi", "hello", "ok", "okay", "yo", "oi", "a"]
    private var vadRatio: Float = 3.5
    private var outputRatio: Float = 1.6
    private var minLevel: Float = 0.0025

    // VAD state
    private var floor: Float = 0.002
    private var speechRun = 0
    private var silenceRun = 0
    private var needPause = false
    private var chunkSeconds = 0.085
    private var preroll: [[Float]] = []
    private let prerollMax = 9           // ≈ 0.75 s before the onset
    private var finishDeadline: DispatchWorkItem?
    private var recentAbandons: [Date] = []
    // The utterance being captured, resampled to 16 kHz mono PCM for Gemini.
    private var utterance: [Int16] = []
    private var resampleCarry: Double = 0
    private var rate: Double = 48000
    // Locale fallback: a recognizer that only ever errors (model missing) is replaced by en-US.
    private var erroredSessions = 0
    private var transcriptsSeen = 0

    // Stats for the periodic log line
    private(set) var statSessions = 0
    private(set) var statAbandoned = 0
    private(set) var statWakes = 0

    var busy: Bool { mode == .command || mode == .finishingCommand }

    init(queue: DispatchQueue) { self.q = queue }

    func configure(locale: String?, extraWords: [String], assistantName: String?,
                   vadRatio: Double?, outputRatio: Double?, minLevel: Double?, debug: Bool) {
        var words: Set<String> = ["alfred", "alfreds", "alfredo", "alfrid", "alfread", "alfried",
                                  "elfred", "alford", "alfret", "alfrede"]
        for w in extraWords + [assistantName ?? ""] {
            let n = WakeEngine.normalize(w)
            if let last = n.last, last.count >= 3 { words.insert(last) }
        }
        strongWords = words
        if let r = vadRatio, r > 1 { self.vadRatio = Float(r) }
        if let r = outputRatio, r >= 1 { self.outputRatio = Float(r) }
        if let m = minLevel, m > 0 { self.minLevel = Float(m) }
        self.debug = debug

        let candidates = [locale, Locale.current.identifier.replacingOccurrences(of: "_", with: "-"), "en-US"].compactMap { $0 }
        for id in candidates {
            if let r = SFSpeechRecognizer(locale: Locale(identifier: id)), r.supportsOnDeviceRecognition {
                recognizer = r
                log("wake: on-device recognizer \(id); wake words \(words.sorted())\(debug ? " [debug on]" : "")")
                return
            }
        }
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
        log("wake: WARNING no on-device recognizer available — falling back to server recognition")
    }

    static func normalize(_ s: String) -> [String] {
        let lowered = s.lowercased()
        let cleaned = String(lowered.unicodeScalars.map {
            CharacterSet.letters.contains($0) || CharacterSet.decimalDigits.contains($0) || $0 == "'" ? Character($0) : " "
        })
        return cleaned.split(separator: " ").map(String.init)
    }

    /// Index of the last word of the wake phrase, if it appears within the first few words.
    /// "Alfred" and its spellings count anywhere there; near-misses the recognizer
    /// sometimes produces ("Albert", "Alfie") only count after "hey"/"ok"/….
    func wakeIndex(_ words: [String]) -> Int? {
        for i in 0..<min(words.count, 4) {
            if strongWords.contains(words[i]) { return i }
            if weakWords.contains(words[i]) && i > 0 && prefixes.contains(words[i - 1]) { return i }
            if i + 1 < words.count, ["al", "all", "el"].contains(words[i]), ["fred", "freed", "fried"].contains(words[i + 1]) {
                return i + 1
            }
        }
        return nil
    }

    func commandText(from transcript: String) -> String {
        let trim = CharacterSet(charactersIn: " ,.!?;:-")
        let raw = transcript.split(separator: " ").map(String.init)
        // Normalization can split one raw word ("Alfred,what's"), so remember
        // which raw word every normalized token came from.
        var flat: [String] = []
        var owner: [Int] = []
        for (i, w) in raw.enumerated() {
            for t in WakeEngine.normalize(w) { flat.append(t); owner.append(i) }
        }
        guard let idx = wakeIndex(flat) else { return transcript.trimmingCharacters(in: trim) }
        return raw.dropFirst(owner[idx] + 1).joined(separator: " ").trimmingCharacters(in: trim)
    }

    // MARK: audio in (on q)

    func reset() {
        cancelTask()
        utterance.removeAll()
        pendingPrefix = ""
        mode = .idle
        speechRun = 0
        silenceRun = 0
        preroll.removeAll()
        needPause = false
    }

    /// Box-filter resample to 16 kHz int16 (enough for speech). `carry` is where
    /// the next output window starts relative to the next chunk; it can be
    /// slightly negative (the window began in the previous chunk), so indices
    /// are clamped to the chunk.
    static func resample(_ x: [Float], rate: Double, carry: inout Double) -> [Int16] {
        guard !x.isEmpty, rate > 0 else { return [] }
        let step = rate / 16000.0
        let n = Double(x.count)
        var out: [Int16] = []
        out.reserveCapacity(Int(n / step) + 1)
        var pos = carry
        while pos + step <= n {
            let a = max(0, Int(pos.rounded(.down)))
            let b = min(x.count, max(Int((pos + step).rounded(.down)), a + 1))
            var sum: Float = 0
            for i in a..<b { sum += x[i] }
            let v = sum / Float(b - a)
            out.append(Int16(max(-1, min(1, v)) * 32767))
            pos += step
        }
        carry = pos - n
        return out
    }

    /// Keep the utterance for the agent (capped at 20 s).
    private func record(_ x: [Float]) {
        guard utterance.count < 16000 * 20 else { return }
        utterance += WakeEngine.resample(x, rate: rate, carry: &resampleCarry)
    }

    func feed(_ samples: [Float], rms: Float, rate: Double) {
        self.rate = rate
        chunkSeconds = Double(samples.count) / rate
        if format == nil || format!.sampleRate != rate {
            format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: rate, channels: 1, interleaved: false)
        }
        // Only the onset is made stricter while the speakers play: once woken,
        // our own chime must not make the user's command look like silence.
        let ratio = vadRatio * (outputActive && mode == .idle ? outputRatio : 1)
        let threshold = max(floor * ratio, minLevel)
        let speech = rms > threshold
        // Adaptive floor: fast to fall, slow to rise so a steady fan is learnt
        // but a sentence is not.
        floor += (rms - floor) * (speech ? 0.002 : 0.05)
        floor = max(floor, 0.0003)
        if speech { speechRun += 1; silenceRun = 0 } else { silenceRun += 1; speechRun = 0 }

        switch mode {
        case .idle:
            preroll.append(samples)
            if preroll.count > prerollMax { preroll.removeFirst() }
            if needPause {
                // A chatty room (TV, a conversation) earns a longer required pause.
                recentAbandons.removeAll { $0.timeIntervalSinceNow < -60 }
                let pauseChunks = recentAbandons.count >= 6 ? 10 : 3
                if silenceRun >= pauseChunks { needPause = false }
                return
            }
            if speechRun >= 2 {
                if debug { log(String(format: "wake: onset rms %.4f floor %.4f thr %.4f%@", rms, floor, threshold, outputActive ? " (speakers busy)" : "")) }
                startSession()
            }
        case .probing:
            append(samples)
            let elapsed = Date().timeIntervalSince(sessionStart)
            if Double(silenceRun) * chunkSeconds >= 0.6 {
                finish(next: .finishingProbe)
            } else if elapsed > 8 && !transcribeAll {
                abandon(reason: "8 s of speech without the wake word")
            }
        case .command:
            append(samples)
            let elapsed = Date().timeIntervalSince(sessionStart)
            let hasCommand = !commandSoFar().isEmpty
            let quiet = Double(silenceRun) * chunkSeconds
            if (hasCommand && quiet >= 1.0) || quiet >= 2.2 || elapsed > 15 {
                finish(next: .finishingCommand)
            }
        case .finishingProbe, .finishingCommand:
            preroll.append(samples)
            if preroll.count > prerollMax { preroll.removeFirst() }
        }
    }

    private func append(_ samples: [Float]) {
        guard !samples.isEmpty else { return }
        record(samples)
        guard let fmt = format, let req = request,
              let buf = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: AVAudioFrameCount(samples.count)) else { return }
        buf.frameLength = AVAudioFrameCount(samples.count)
        samples.withUnsafeBufferPointer { src in
            buf.floatChannelData![0].update(from: src.baseAddress!, count: samples.count)
        }
        req.append(buf)
    }

    private func startSession(continuing: Bool = false) {
        guard let rec = recognizer else { return }
        if !continuing { utterance.removeAll(); resampleCarry = 0 }
        guard rec.isAvailable else {
            if debug { log("wake: recognizer not available right now") }
            needPause = true
            return
        }
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        if rec.supportsOnDeviceRecognition { req.requiresOnDeviceRecognition = true }
        req.contextualStrings = ["Alfred", "Hey Alfred", "OK Alfred"]
        req.addsPunctuation = false
        sessionID += 1
        statSessions += 1
        let sid = sessionID
        request = req
        lastText = ""
        sessionStart = Date()
        mode = continuing ? .command : .probing
        task = rec.recognitionTask(with: req) { [weak self] result, error in
            guard let self = self else { return }
            let text = result?.bestTranscription.formattedString
            let final = result?.isFinal ?? false
            self.q.async { self.handle(sid: sid, text: text, final: final, error: error) }
        }
        for chunk in preroll { append(chunk) }
        preroll.removeAll()
    }

    private func handle(sid: Int, text: String?, final: Bool, error: Error?) {
        guard sid == sessionID else { return }
        if let t = text, !t.isEmpty { lastText = t; transcriptsSeen += 1 }
        if let e = error as NSError?, text == nil, e.code != 1110, e.code != 216, e.code != 301 {
            erroredSessions += 1
            if debug || erroredSessions <= 3 { log("wake: recognizer error \(e.domain) \(e.code): \(e.localizedDescription)") }
            if erroredSessions >= 4 && transcriptsSeen == 0,
               let current = recognizer?.locale.identifier, !current.hasPrefix("en-US"),
               let fallback = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), fallback.supportsOnDeviceRecognition {
                recognizer = fallback
                erroredSessions = 0
                log("wake: \(current) recognizer keeps failing — switched to en-US")
            }
        }
        let words = WakeEngine.normalize(lastText)

        if transcribeAll, let t = text, !t.isEmpty { onUtterance?(t) }

        switch mode {
        case .probing, .finishingProbe:
            if wakeIndex(words) != nil {
                statWakes += 1
                if debug { log("wake: matched in “\(lastText)”") }
                if mode == .probing {
                    enterCommand()
                } else {
                    // Heard only in the final result: the user paused after
                    // "Hey Alfred" (waiting for the chime). Keep listening for
                    // the command in a fresh recognizer session.
                    let said = commandText(from: lastText)
                    onWake?()
                    finishDeadline?.cancel()
                    cancelTask()
                    sessionID += 1
                    startSession(continuing: true)
                    if mode == .command {
                        silenceRun = 0
                        pendingPrefix = said
                    } else {
                        deliver(said)
                    }
                }
                return
            }
            if mode == .probing && words.count >= 6 && !transcribeAll {
                abandon(reason: debug ? "no wake word in “\(lastText)”" : nil)
                return
            }
            if final || error != nil {
                if debug {
                    let why = error.map { " (error: \(($0 as NSError).code))" } ?? ""
                    log("wake: heard “\(lastText)”\(why) — not for me")
                }
                endSession()
            }
        case .command, .finishingCommand:
            if mode == .finishingCommand && (final || error != nil) {
                deliver(commandSoFar())
            }
        case .idle:
            break
        }
    }

    private func enterCommand() {
        mode = .command
        sessionStart = Date()
        silenceRun = 0
        onWake?()
    }

    /// Finish the recognizer and wait (briefly) for its final transcript.
    private func finish(next: Mode) {
        mode = next
        request?.endAudio()
        let sid = sessionID
        let work = DispatchWorkItem { [weak self] in
            guard let self = self, self.sessionID == sid else { return }
            if self.mode == .finishingCommand {
                self.deliver(self.commandSoFar())
            } else if self.mode == .finishingProbe {
                if self.debug { log("wake: no final result; last heard “\(self.lastText)”") }
                self.endSession()
            }
        }
        finishDeadline?.cancel()
        finishDeadline = work
        q.asyncAfter(deadline: .now() + 2.0, execute: work)
    }

    /// Words spoken after the wake word across both sessions of a paused request.
    private var pendingPrefix = ""

    private func commandSoFar() -> String {
        let tail = commandText(from: lastText)
        return [pendingPrefix, tail].filter { !$0.isEmpty }.joined(separator: " ")
    }

    private func deliver(_ command: String) {
        finishDeadline?.cancel()
        let audio = utterance
        utterance.removeAll()
        pendingPrefix = ""
        endSession()
        onCommand?(command, audio)
    }

    private func abandon(reason: String?) {
        if let r = reason { log("wake: \(r)") }
        statAbandoned += 1
        recentAbandons.append(Date())
        endSession()
        needPause = true
    }

    private func endSession() {
        cancelTask()
        sessionID += 1
        mode = .idle
    }

    private func cancelTask() {
        task?.cancel()
        task = nil
        request = nil
    }

    func takeStats() -> (Int, Int, Int) {
        defer { statSessions = 0; statAbandoned = 0; statWakes = 0 }
        return (statSessions, statAbandoned, statWakes)
    }
}

// Microphone capture straight from the HAL (AUHAL).
//
// Why not AVAudioEngine / AudioQueue: both run the device IO at its default
// ~512-frame cycle and resample, which measured 0.28–0.38 % of a core on an M4.
// Asking the HAL for a 4096-frame IO buffer (≈85 ms at 48 kHz) and doing no
// conversion beyond a mono mixdown measured 0.03 %. Latency is irrelevant for a
// wake word, so the big buffer is pure win.
import AudioToolbox
import CoreAudio
import Foundation

final class Mic {
    /// Called on the HAL IO thread with mono float samples and their RMS.
    var onChunk: ((UnsafePointer<Float>, Int, Float) -> Void)?
    private(set) var running = false
    private(set) var sampleRate: Double = 48000

    private var unit: AudioUnit?
    private let scratch = UnsafeMutablePointer<Float>.allocate(capacity: 16384)
    private var listenerInstalled = false
    private let queue: DispatchQueue

    init(queue: DispatchQueue) { self.queue = queue }

    private static func defaultInputDevice() -> AudioDeviceID {
        var dev = AudioDeviceID(0)
        var size = UInt32(MemoryLayout<AudioDeviceID>.size)
        var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultInputDevice,
                                              mScope: kAudioObjectPropertyScopeGlobal,
                                              mElement: kAudioObjectPropertyElementMain)
        AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &dev)
        return dev
    }

    private func installDeviceListener() {
        guard !listenerInstalled else { return }
        listenerInstalled = true
        var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultInputDevice,
                                              mScope: kAudioObjectPropertyScopeGlobal,
                                              mElement: kAudioObjectPropertyElementMain)
        AudioObjectAddPropertyListenerBlock(AudioObjectID(kAudioObjectSystemObject), &addr, queue) { [weak self] _, _ in
            guard let self = self, self.running else { return }
            log("mic: default input changed — restarting capture")
            self.stop()
            _ = self.start()
        }
    }

    func start() -> Bool {
        guard !running else { return true }
        installDeviceListener()
        var desc = AudioComponentDescription(componentType: kAudioUnitType_Output,
                                             componentSubType: kAudioUnitSubType_HALOutput,
                                             componentManufacturer: kAudioUnitManufacturer_Apple,
                                             componentFlags: 0, componentFlagsMask: 0)
        guard let comp = AudioComponentFindNext(nil, &desc) else { log("mic: no HAL unit"); return false }
        var au: AudioUnit?
        guard AudioComponentInstanceNew(comp, &au) == noErr, let unit = au else { log("mic: unit create failed"); return false }

        var one: UInt32 = 1, zero: UInt32 = 0
        AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO, kAudioUnitScope_Input, 1, &one, 4)
        AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO, kAudioUnitScope_Output, 0, &zero, 4)

        var dev = Mic.defaultInputDevice()
        if dev == 0 { log("mic: no input device"); AudioComponentInstanceDispose(unit); return false }
        AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice, kAudioUnitScope_Global, 0,
                             &dev, UInt32(MemoryLayout<AudioDeviceID>.size))

        // Large IO buffer = few wakeups. Clamp to what the device allows.
        var range = AudioValueRange()
        var rsize = UInt32(MemoryLayout<AudioValueRange>.size)
        var raddr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyBufferFrameSizeRange,
                                               mScope: kAudioObjectPropertyScopeGlobal,
                                               mElement: kAudioObjectPropertyElementMain)
        var frames: UInt32 = 4096
        if AudioObjectGetPropertyData(dev, &raddr, 0, nil, &rsize, &range) == noErr, range.mMaximum > 0 {
            frames = UInt32(min(max(Double(frames), range.mMinimum), range.mMaximum))
        }
        var baddr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyBufferFrameSize,
                                               mScope: kAudioObjectPropertyScopeGlobal,
                                               mElement: kAudioObjectPropertyElementMain)
        AudioObjectSetPropertyData(dev, &baddr, 0, nil, 4, &frames)
        var maxFrames: UInt32 = 8192
        AudioUnitSetProperty(unit, kAudioUnitProperty_MaximumFramesPerSlice, kAudioUnitScope_Global, 0, &maxFrames, 4)

        var hw = AudioStreamBasicDescription()
        var hsize = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
        AudioUnitGetProperty(unit, kAudioUnitProperty_StreamFormat, kAudioUnitScope_Input, 1, &hw, &hsize)
        sampleRate = hw.mSampleRate > 0 ? hw.mSampleRate : 48000
        var fmt = AudioStreamBasicDescription(mSampleRate: sampleRate, mFormatID: kAudioFormatLinearPCM,
                                              mFormatFlags: kAudioFormatFlagIsFloat | kAudioFormatFlagIsPacked | kAudioFormatFlagIsNonInterleaved,
                                              mBytesPerPacket: 4, mFramesPerPacket: 1, mBytesPerFrame: 4,
                                              mChannelsPerFrame: 1, mBitsPerChannel: 32, mReserved: 0)
        AudioUnitSetProperty(unit, kAudioUnitProperty_StreamFormat, kAudioUnitScope_Output, 1, &fmt, hsize)

        var cb = AURenderCallbackStruct(inputProc: { refCon, flags, ts, bus, n, _ in
            let mic = Unmanaged<Mic>.fromOpaque(refCon).takeUnretainedValue()
            return mic.render(flags, ts, bus, n)
        }, inputProcRefCon: Unmanaged.passUnretained(self).toOpaque())
        AudioUnitSetProperty(unit, kAudioOutputUnitProperty_SetInputCallback, kAudioUnitScope_Global, 0,
                             &cb, UInt32(MemoryLayout<AURenderCallbackStruct>.size))

        guard AudioUnitInitialize(unit) == noErr else { log("mic: init failed"); AudioComponentInstanceDispose(unit); return false }
        let st = AudioOutputUnitStart(unit)
        guard st == noErr else { log("mic: start failed \(st)"); AudioUnitUninitialize(unit); AudioComponentInstanceDispose(unit); return false }
        self.unit = unit
        running = true
        log("mic: capturing at \(Int(sampleRate)) Hz, IO buffer \(frames) frames")
        return true
    }

    private func render(_ flags: UnsafeMutablePointer<AudioUnitRenderActionFlags>,
                        _ ts: UnsafePointer<AudioTimeStamp>, _ bus: UInt32, _ n: UInt32) -> OSStatus {
        guard let unit = unit, n <= 8192 else { return noErr }
        var abl = AudioBufferList(mNumberBuffers: 1,
                                  mBuffers: AudioBuffer(mNumberChannels: 1, mDataByteSize: n * 4, mData: scratch))
        let st = AudioUnitRender(unit, flags, ts, bus, n, &abl)
        if st != noErr { return st }
        var sum: Float = 0
        let count = Int(n)
        for i in 0..<count { let v = scratch[i]; sum += v * v }
        onChunk?(scratch, count, (sum / Float(max(count, 1))).squareRoot())
        return noErr
    }

    func stop() {
        guard let unit = unit else { running = false; return }
        AudioOutputUnitStop(unit)
        AudioUnitUninitialize(unit)
        AudioComponentInstanceDispose(unit)
        self.unit = nil
        running = false
        log("mic: released")
    }
}

/// Tells us when the Mac's speakers are in use (by anyone). Event-driven:
/// CoreAudio calls back when the default output starts/stops running or changes.
final class OutputWatcher {
    var onChange: ((Bool) -> Void)?
    private let queue: DispatchQueue
    private var device = AudioDeviceID(0)
    private var runningAddr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyDeviceIsRunningSomewhere,
                                                         mScope: kAudioObjectPropertyScopeGlobal,
                                                         mElement: kAudioObjectPropertyElementMain)
    private var block: AudioObjectPropertyListenerBlock?

    init(queue: DispatchQueue) { self.queue = queue }

    func start() {
        var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultOutputDevice,
                                              mScope: kAudioObjectPropertyScopeGlobal,
                                              mElement: kAudioObjectPropertyElementMain)
        AudioObjectAddPropertyListenerBlock(AudioObjectID(kAudioObjectSystemObject), &addr, queue) { [weak self] _, _ in
            self?.attach()
        }
        attach()
    }

    private func attach() {
        if device != 0, let b = block {
            AudioObjectRemovePropertyListenerBlock(device, &runningAddr, queue, b)
        }
        var dev = AudioDeviceID(0)
        var size = UInt32(MemoryLayout<AudioDeviceID>.size)
        var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultOutputDevice,
                                              mScope: kAudioObjectPropertyScopeGlobal,
                                              mElement: kAudioObjectPropertyElementMain)
        AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &dev)
        device = dev
        let b: AudioObjectPropertyListenerBlock = { [weak self] _, _ in self?.report() }
        block = b
        if dev != 0 { AudioObjectAddPropertyListenerBlock(dev, &runningAddr, queue, b) }
        report()
    }

    private func report() {
        var running: UInt32 = 0
        var size = UInt32(MemoryLayout<UInt32>.size)
        if device != 0 { AudioObjectGetPropertyData(device, &runningAddr, 0, nil, &size, &running) }
        onChange?(running != 0)
    }
}

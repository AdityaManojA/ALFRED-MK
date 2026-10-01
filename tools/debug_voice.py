#!/usr/bin/env python3
"""
tools/debug_voice.py — Comprehensive Voice, Microphone, Wake Word & TTS Diagnostic Tool for ALFRED.

Usage:
    py tools/debug_voice.py                      # Interactive diagnostic menu
    py tools/debug_voice.py --devices            # List audio input/output devices & config
    py tools/debug_voice.py --mic                # Live mic VU meter & RMS test (default device)
    py tools/debug_voice.py --mic 2              # Live mic test on device index 2
    py tools/debug_voice.py --wake               # Live OpenWakeWord score test for 'Alfred'
    py tools/debug_voice.py --tts                # Test TTS synthesis & speaker output
    py tools/debug_voice.py --tts "Hello sir"    # Test custom phrase via TTS
    py tools/debug_voice.py --set-mic 2          # Save device 2 as default microphone
    py tools/debug_voice.py --set-spk 4          # Save device 4 as default speaker
    py tools/debug_voice.py --all                # Run all diagnostics sequentially
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

# Ensure project root is in sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"   {title}")
    print("=" * 70)


def list_audio_devices() -> None:
    """Print all input and output devices with current ALFRED config status."""
    _banner("AUDIO DEVICE INVENTORY & CONFIGURATION")
    try:
        import sounddevice as sd
        from core import audio_devices
        from memory.config_manager import get_input_device, get_output_device
    except ImportError as e:
        print(f"[ERROR] Could not import audio dependencies: {e}")
        return

    saved_mic = get_input_device()
    saved_spk = get_output_device()

    print(f"ALFRED Configured Input Device  : '{saved_mic}' (Empty = System Default)")
    print(f"ALFRED Configured Output Device : '{saved_spk}' (Empty = System Default)")

    try:
        hostapis = sd.query_hostapis()
        default_in = sd.default.device[0]
        default_out = sd.default.device[1]
    except Exception as e:
        print(f"[WARN] Failed to query host APIs: {e}")
        hostapis = []
        default_in, default_out = -1, -1

    all_devs = sd.query_devices()

    print("\n--- INPUT DEVICES (Microphones) ---")
    in_count = 0
    for idx, d in enumerate(all_devs):
        if d.get("max_input_channels", 0) > 0:
            in_count += 1
            api_name = hostapis[d["hostapi"]]["name"] if d.get("hostapi", -1) < len(hostapis) else "Unknown"
            is_os_def = " [OS DEFAULT]" if idx == default_in else ""
            is_alfred = " [*ALFRED TARGET*]" if saved_mic and (saved_mic.lower() in d["name"].lower()) else ""
            print(f"  [{idx:2d}] {d['name']} | API: {api_name} | Chans: {d['max_input_channels']} | {d['default_samplerate']:.0f}Hz{is_os_def}{is_alfred}")
    if in_count == 0:
        print("  [NONE DETECTED]")

    print("\n--- OUTPUT DEVICES (Speakers / Headphones) ---")
    out_count = 0
    for idx, d in enumerate(all_devs):
        if d.get("max_output_channels", 0) > 0:
            out_count += 1
            api_name = hostapis[d["hostapi"]]["name"] if d.get("hostapi", -1) < len(hostapis) else "Unknown"
            is_os_def = " [OS DEFAULT]" if idx == default_out else ""
            is_alfred = " [*ALFRED TARGET*]" if saved_spk and (saved_spk.lower() in d["name"].lower()) else ""
            print(f"  [{idx:2d}] {d['name']} | API: {api_name} | Chans: {d['max_output_channels']} | {d['default_samplerate']:.0f}Hz{is_os_def}{is_alfred}")
    if out_count == 0:
        print("  [NONE DETECTED]")

    # Check resolution
    res_mic = audio_devices.resolve(saved_mic, "input") if saved_mic else default_in
    res_spk = audio_devices.resolve(saved_spk, "output") if saved_spk else default_out
    print("\n--- RESOLUTION CHECK ---")
    print(f"Active Resolved Mic Device Index : {res_mic} ({all_devs[res_mic]['name'] if 0 <= res_mic < len(all_devs) else 'Unknown'})")
    print(f"Active Resolved Spk Device Index : {res_spk} ({all_devs[res_spk]['name'] if 0 <= res_spk < len(all_devs) else 'Unknown'})")


def test_microphone(device: Optional[int | str] = None, duration_s: float = 12.0) -> None:
    """Test live microphone level and display an ASCII VU meter with RMS."""
    _banner("LIVE MICROPHONE VU METER TEST")
    try:
        import numpy as np
        import sounddevice as sd
        from core import audio_devices
        from memory.config_manager import get_input_device
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return

    # Determine target device
    dev_idx = None
    dev_name = "System Default"
    if device is not None:
        try:
            dev_idx = int(device)
            dev_name = sd.query_devices(dev_idx)["name"]
        except ValueError:
            dev_idx = audio_devices.resolve(str(device), "input")
            dev_name = str(device)
    else:
        saved = get_input_device()
        if saved:
            dev_idx = audio_devices.resolve(saved, "input")
            dev_name = f"{saved} (Configured)"
        else:
            dev_idx = sd.default.device[0]
            dev_name = f"{sd.query_devices(dev_idx)['name']} (OS Default)"

    print(f"Listening on device [{dev_idx}]: '{dev_name}'")
    print(f"Sampling: 16000 Hz, mono, int16. Speak into your microphone now...")
    print(f"Press Ctrl+C to stop (Auto-stops after {duration_s:.0f}s)\n")

    rms_samples: list[float] = []
    peak_rms = 0.0

    def _audio_callback(indata, frames, time_info, status):
        nonlocal peak_rms
        data = indata[:, 0].astype(np.float32)
        rms = float(np.sqrt(np.mean(data ** 2)))
        rms_samples.append(rms)
        peak_rms = max(peak_rms, rms)

        # Build ASCII volume bar
        # RMS ranges typically: 0 (silence) to 5000+ (loud)
        bar_len = min(35, int(rms / 120))
        bar = "#" * bar_len + "-" * (35 - bar_len)
        
        status_tag = "[SILENCE]"
        if rms > 2000:
            status_tag = "[LOUD]       "
        elif rms > 400:
            status_tag = "[GOOD SPEECH]"
        elif rms > 80:
            status_tag = "[WHISPER]    "

        sys.stdout.write(f"\rVU: [{bar}] RMS: {rms:6.1f} | Peak: {peak_rms:6.1f} | {status_tag}")
        sys.stdout.flush()

    try:
        with sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="int16",
            blocksize=1280,  # 80ms chunks
            device=dev_idx,
            callback=_audio_callback,
        ):
            t_end = time.monotonic() + duration_s
            while time.monotonic() < t_end:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[Stopped by user]")
    except Exception as e:
        print(f"\n[ERROR] Microphone stream failed: {e}")
        return

    print("\n\n--- MICROPHONE TEST SUMMARY ---")
    if rms_samples:
        avg_rms = sum(rms_samples) / len(rms_samples)
        print(f"Average RMS: {avg_rms:.1f} | Peak RMS: {peak_rms:.1f}")
        if peak_rms < 100:
            print("[DIAGNOSIS]: Microphone signal is EXTREMELY WEAK or SILENT.")
            print("Troubleshooting:")
            print("1. Check if the microphone hardware switch or headset mute is toggled ON.")
            print("2. Check Windows Sound Settings > Input Volume (ensure mic volume is >= 80%).")
            print("3. Ensure the correct microphone is selected (e.g. AB13X USB vs Realtek).")
        elif peak_rms < 400:
            print("[DIAGNOSIS]: Microphone is picking up audio, but signal is FAINT.")
            print("Recommendation: Increase Windows microphone input gain or speak closer to mic.")
        else:
            print("[DIAGNOSIS]: Microphone level is HEALTHY and clearly capturing speech! ✓")
    else:
        print("[DIAGNOSIS]: No audio frames were received from the device.")


def test_wake_word(device: Optional[int | str] = None, duration_s: float = 25.0) -> None:
    """Test live hybrid wake-word detection (Acoustic + Speech Verifier) for 'Alfred' / 'Hey Alfred'."""
    _banner("LIVE WAKE WORD ('ALFRED' / 'HEY ALFRED') RECOGNITION TEST")
    try:
        import numpy as np
        import sounddevice as sd
        from core import audio_devices
        from core.wake_word import DEFAULT_THRESHOLD, WAKE_PHRASE, WakeWordDetector
        from memory.config_manager import get_input_device
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return

    dev_idx = None
    dev_name = "System Default"
    if device is not None:
        try:
            dev_idx = int(device)
            dev_name = sd.query_devices(dev_idx)["name"]
        except ValueError:
            dev_idx = audio_devices.resolve(str(device), "input")
            dev_name = str(device)
    else:
        saved = get_input_device()
        if saved:
            dev_idx = audio_devices.resolve(saved, "input")
            dev_name = f"{saved} (Configured)"
        else:
            dev_idx = sd.default.device[0]
            dev_name = f"{sd.query_devices(dev_idx)['name']} (OS Default)"

    print(f"Initializing Hybrid Wake Word Detector for '{WAKE_PHRASE}' / 'Hey {WAKE_PHRASE}'...")
    detections = 0

    def _on_detected():
        nonlocal detections
        detections += 1
        print(f"\n[>>> WAKE DETECTED! <<<] Triggered successfully! (Detection #{detections})\n")

    detector = WakeWordDetector(
        on_detect=_on_detected,
        threshold=DEFAULT_THRESHOLD,
        logger=lambda m: print(f"  {m}"),
    )
    if not detector.start():
        print("[ERROR] Failed to start WakeWordDetector.")
        return

    print(f"Detector active. Listening on device [{dev_idx}]: '{dev_name}'")
    print(f"Say 'Alfred' or 'Hey Alfred' into your microphone...")
    print(f"Press Ctrl+C to stop (Auto-stops after {duration_s:.0f}s)\n")

    def _audio_callback(indata, frames, time_info, status):
        detector.feed(indata)

    try:
        with sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="int16",
            blocksize=1280,
            device=dev_idx,
            callback=_audio_callback,
        ):
            t_end = time.monotonic() + duration_s
            while time.monotonic() < t_end:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[Stopped by user]")
    except Exception as e:
        print(f"\n[ERROR] Stream failed: {e}")
        detector.stop()
        return
    finally:
        detector.stop()

    print("\n--- WAKE WORD TEST SUMMARY ---")
    print(f"Total Wake Triggers : {detections}")
    if detections > 0:
        print("[RESULT]: Wake word detection is WORKING PROPERLY! ✓")
    else:
        print("[RESULT]: 'Alfred' was NOT detected.")
        print("Troubleshooting:")
        print("1. Run microphone test (`py tools/debug_voice.py --mic`) to check mic volume.")
        print("2. Ensure the active input device matches the microphone you are speaking into.")


def test_tts(phrase: Optional[str] = None, engine_name: str = "default") -> None:
    """Test speech synthesis and playback through configured speakers."""
    _banner("TEXT-TO-SPEECH (TTS) & AUDIO OUTPUT TEST")
    try:
        import sounddevice as sd
        from core import audio_devices
        from core.tts import get_engine
        from memory.config_manager import get_output_device
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return

    saved_spk = get_output_device()
    resolved_spk = audio_devices.resolve(saved_spk, "output") if saved_spk else sd.default.device[1]
    dev_info = sd.query_devices(resolved_spk) if resolved_spk is not None else None
    spk_label = dev_info["name"] if dev_info else "System Default"

    text = phrase or "All tactical audio matrices nominal, sir. Speech synthesis and output streams are fully operational."
    print(f"Target Output Device : [{resolved_spk}] '{spk_label}'")
    print(f"TTS Engine           : '{engine_name}'")
    print(f"Test Utterance       : \"{text}\"")
    print("\nSynthesizing and playing speech...")

    t0 = time.perf_counter()
    try:
        engine = get_engine(engine_name)
        engine.speak(text)
        duration = time.perf_counter() - t0
        print(f"\n[TTS RESULT]: Playback completed successfully in {duration:.2f} seconds! ✓")
    except Exception as exc:
        print(f"\n[TTS ERROR]: Speech playback failed: {exc}")
        import traceback
        traceback.print_exc()


def set_active_device(kind: str, dev_arg: str | int) -> None:
    """Set and save active audio input or output device in config."""
    try:
        import sounddevice as sd
        from memory.config_manager import set_input_device, set_output_device
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return

    all_devs = sd.query_devices()
    try:
        idx = int(dev_arg)
        if 0 <= idx < len(all_devs):
            dev_name = all_devs[idx]["name"]
        else:
            print(f"[ERROR] Device index {idx} out of range (0-{len(all_devs)-1})")
            return
    except ValueError:
        dev_name = str(dev_arg)

    if kind == "input":
        set_input_device(dev_name)
        print(f"[SUCCESS] Saved Input Device (Microphone): '{dev_name}'")
    else:
        set_output_device(dev_name)
        print(f"[SUCCESS] Saved Output Device (Speaker): '{dev_name}'")


def interactive_menu() -> None:
    """Display interactive CLI menu for debugging."""
    while True:
        _banner("ALFRED VOICE & AUDIO DIAGNOSTIC TOOL")
        print("  1. List Audio Devices & Current Config")
        print("  2. Test Live Microphone VU Meter (Level & Noise Floor)")
        print("  3. Test Wake Word ('Alfred') with Real-Time Prediction Scores")
        print("  4. Test Text-to-Speech (TTS) & Speaker Playback")
        print("  5. Select & Save Active Microphone")
        print("  6. Select & Save Active Speaker")
        print("  7. Run Full Audio Health Check")
        print("  0. Exit")
        print("-" * 70)
        
        choice = input("Select an option (0-7): ").strip()
        if choice == "1":
            list_audio_devices()
        elif choice == "2":
            dev = input("Enter device index (or press Enter for default): ").strip()
            test_microphone(device=dev if dev else None)
        elif choice == "3":
            dev = input("Enter device index (or press Enter for default): ").strip()
            test_wake_word(device=dev if dev else None)
        elif choice == "4":
            phrase = input("Enter phrase to speak (or press Enter for default): ").strip()
            test_tts(phrase=phrase if phrase else None)
        elif choice == "5":
            list_audio_devices()
            dev = input("Enter device index to save as Microphone: ").strip()
            if dev:
                set_active_device("input", dev)
        elif choice == "6":
            list_audio_devices()
            dev = input("Enter device index to save as Speaker: ").strip()
            if dev:
                set_active_device("output", dev)
        elif choice == "7":
            list_audio_devices()
            print("\nStep 1/3: Testing microphone for 5 seconds...")
            test_microphone(duration_s=5.0)
            print("\nStep 2/3: Testing wake word for 8 seconds...")
            test_wake_word(duration_s=8.0)
            print("\nStep 3/3: Testing TTS audio output...")
            test_tts()
        elif choice == "0" or choice.lower() in ("exit", "quit", "q"):
            print("Exiting diagnostic tool. Goodbye!")
            break
        else:
            print("[WARN] Invalid option. Please select 0-7.")

        input("\nPress Enter to continue...")


def main() -> None:
    parser = argparse.ArgumentParser(description="ALFRED Voice & Audio Diagnostic Tool")
    parser.add_argument("--devices", "-d", action="store_true", help="List audio devices & current configuration")
    parser.add_argument("--mic", "-m", nargs="?", const="default", help="Test live microphone VU meter [optional: device index/name]")
    parser.add_argument("--wake", "-w", nargs="?", const="default", help="Test live wake word detection [optional: device index/name]")
    parser.add_argument("--tts", "-t", nargs="?", const="default", help="Test speech output [optional: phrase to speak]")
    parser.add_argument("--set-mic", help="Set and save microphone by device index or name")
    parser.add_argument("--set-spk", help="Set and save speaker by device index or name")
    parser.add_argument("--all", "-a", action="store_true", help="Run full diagnostic suite")

    args = parser.parse_args()

    # If no flags passed, launch interactive menu
    if not any(vars(args).values()):
        interactive_menu()
        return

    if args.devices:
        list_audio_devices()
    if args.set_mic:
        set_active_device("input", args.set_mic)
    if args.set_spk:
        set_active_device("output", args.set_spk)
    if args.mic is not None:
        dev = None if args.mic == "default" else args.mic
        test_microphone(device=dev)
    if args.wake is not None:
        dev = None if args.wake == "default" else args.wake
        test_wake_word(device=dev)
    if args.tts is not None:
        phrase = None if args.tts == "default" else args.tts
        test_tts(phrase=phrase)
    if args.all:
        list_audio_devices()
        test_microphone(duration_s=5.0)
        test_wake_word(duration_s=8.0)
        test_tts()


if __name__ == "__main__":
    main()

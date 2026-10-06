"""
tools/enroll_voice.py — Interactive Voice Profile Enrollment CLI for ALFRED.

Enrolls, lists, or deletes local speaker verification voice profiles for ALFRED.
Uses pre-trained neural speaker embedding model (CAM++) to extract and calibrate
speaker identity from 2-3 short "Hey Alfred" utterances.

Saved profiles reside locally in ~/.alfred/voice_profiles/ and are NEVER uploaded.

Usage:
  # Interactive microphone enrollment (3 samples)
  python tools/enroll_voice.py --enroll <user_name>

  # Enroll from existing recorded WAV files
  python tools/enroll_voice.py --from-wavs <wav1> <wav2> <wav3> --user <user_name>

  # List enrolled voice profiles
  python tools/enroll_voice.py --list

  # Delete an enrolled voice profile
  python tools/enroll_voice.py --delete <user_name>

  # Benchmark speaker verification extraction on local hardware
  python tools/enroll_voice.py --benchmark
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from core.speaker.types import SpeakerProfile
from core.speaker.profile_store import SpeakerProfileStore, get_default_profile_store
from core.speaker.extractor import SpeakerEmbeddingExtractor, CampplusOnnxExtractor
from core.speaker.enrollment import (
    SpeakerEnrollmentManager,
    EnrollmentResult,
    validate_utterance_quality,
)

SAMPLE_RATE = 16000
RECORD_DURATION_S = 2.0


def record_clip(duration_s: float = RECORD_DURATION_S) -> np.ndarray:
    """Record mono 16 kHz float32 audio from default input device."""
    import sounddevice as sd

    samples_n = int(duration_s * SAMPLE_RATE)
    recording = sd.rec(samples_n, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    return recording.flatten()


def enroll_interactive(
    user_name: str,
    profile_store: Optional[SpeakerProfileStore] = None,
    extractor: Optional[SpeakerEmbeddingExtractor] = None,
    target_samples: int = 3,
) -> bool:
    """Interactively guide user through recording enrollment utterances."""
    store = profile_store or get_default_profile_store()
    ext = extractor or CampplusOnnxExtractor()
    mgr = SpeakerEnrollmentManager(profile_store=store, embedding_extractor=ext, target_samples=target_samples)

    clean_name = user_name.strip()
    if not clean_name:
        print("❌ Error: User name cannot be empty.")
        return False

    print("\n" + "=" * 65)
    print(f"🎙️  ALFRED VOICE BIOMETRIC ENROLLMENT: {clean_name}")
    print("=" * 65)
    print("Instructions:")
    print("  • You will be prompted to speak 'Hey Alfred' 3 times.")
    print("  • Speak clearly in your natural voice.")
    print("  • The system verifies acoustic quality and inter-sample consistency.\n")

    accepted_audio = []
    attempt = 1
    sample_idx = 1

    while sample_idx <= target_samples:
        prompt_suffix = ""
        if sample_idx == 2:
            prompt_suffix = " (vary distance or tone slightly)"
        elif sample_idx == 3:
            prompt_suffix = " (one final sample to calibrate threshold)"

        input(f"[{sample_idx}/{target_samples}] Press ENTER, then immediately say 'Hey Alfred'{prompt_suffix}...")
        print(f"  🔴 Recording ({RECORD_DURATION_S:.1f}s)... ", end="", flush=True)

        audio = record_clip(RECORD_DURATION_S)
        print("Done!")

        # Validate quality
        val = validate_utterance_quality(audio, SAMPLE_RATE)
        if not val.ok:
            print(f"  ⚠️  Quality Check Failed: {val.message}")
            print("      Please repeat this sample.\n")
            attempt += 1
            if attempt > 8:
                print("❌ Too many failed attempts. Enrollment aborted.")
                return False
            continue

        accepted_audio.append(audio)
        sample_idx += 1
        print(f"  ✓ Sample {sample_idx - 1} captured successfully.\n")

    print("⏳ Analyzing samples and calibrating personal speaker threshold...")
    res = mgr.enroll_user(clean_name, accepted_audio, sample_rate=SAMPLE_RATE)
    if not res.success:
        print(f"❌ Enrollment Failed: {res.error_message}")
        return False

    prof = res.profile
    print("\n🎉 ENROLLMENT SUCCESSFUL!")
    print(f"  • Profile ID:           {prof.profile_id}")
    print(f"  • User Name:            {prof.user_name}")
    print(f"  • Samples Count:        {prof.sample_count}")
    print(f"  • Calibrated Threshold: {prof.threshold:.3f}")
    if res.pairwise_similarities:
        avg_sim = float(np.mean(res.pairwise_similarities))
        print(f"  • Consistency Score:    {avg_sim * 100:.1f}%")
    print(f"  • Profile Storage:      {store.storage_dir / (prof.profile_id + '.json')}")
    print("\nHands-free wake ('Hey Alfred') is now armed for this voice profile.\n")
    return True


def enroll_from_files(
    user_name: str,
    wav_paths: List[str],
    profile_store: Optional[SpeakerProfileStore] = None,
    extractor: Optional[SpeakerEmbeddingExtractor] = None,
) -> EnrollmentResult:
    """Enroll a user from existing WAV files."""
    import scipy.io.wavfile as wavfile

    store = profile_store or get_default_profile_store()
    ext = extractor or CampplusOnnxExtractor()
    mgr = SpeakerEnrollmentManager(profile_store=store, embedding_extractor=ext, target_samples=len(wav_paths))

    audio_samples = []
    for p in wav_paths:
        path = Path(p)
        if not path.is_file():
            return EnrollmentResult(success=False, error_message=f"File not found: {p}")
        sr, dat = wavfile.read(str(path))
        if dat.ndim > 1:
            dat = dat[:, 0]
        # Resample if not 16000
        if sr != SAMPLE_RATE:
            num_samples = int(len(dat) * SAMPLE_RATE / sr)
            import scipy.signal
            dat = scipy.signal.resample(dat, num_samples).astype(dat.dtype)
        audio_samples.append(dat)

    return mgr.enroll_user(user_name, audio_samples, sample_rate=SAMPLE_RATE)


def list_enrolled_profiles(profile_store: Optional[SpeakerProfileStore] = None) -> List[SpeakerProfile]:
    store = profile_store or get_default_profile_store()
    return store.list_profiles()


def delete_enrolled_profile(user_name: str, profile_store: Optional[SpeakerProfileStore] = None) -> bool:
    store = profile_store or get_default_profile_store()
    return store.delete_profile(user_name)


def main():
    parser = argparse.ArgumentParser(description="ALFRED Voice Biometric Profile Manager")
    parser.add_argument("--enroll", metavar="NAME", help="Interactively enroll voice profile for NAME")
    parser.add_argument("--from-wavs", nargs="+", metavar="WAV", help="Enroll from existing WAV files")
    parser.add_argument("--user", metavar="NAME", help="User name when using --from-wavs")
    parser.add_argument("--list", action="store_true", help="List enrolled voice profiles")
    parser.add_argument("--delete", metavar="NAME", help="Delete voice profile for NAME")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark neural speaker embedding latency")

    args = parser.parse_args()

    store = get_default_profile_store()

    if args.list:
        profiles = list_enrolled_profiles(store)
        print("\n" + "=" * 65)
        print(f"ENROLLED ALFRED VOICE PROFILES ({len(profiles)} total)")
        print("=" * 65)
        if not profiles:
            print("  No voice profiles currently enrolled.")
            print("  Hands-free wake requires enrollment: py tools/enroll_voice.py --enroll <name>")
        else:
            for p in profiles:
                dt = datetime.fromtimestamp(p.enrolled_at).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  • User:      {p.user_name} ({p.profile_id})")
                print(f"    Created:   {dt}")
                print(f"    Samples:   {p.sample_count}")
                print(f"    Threshold: {p.threshold:.3f}")
                print(f"    Path:      {store.storage_dir / (p.profile_id + '.json')}\n")
        return

    if args.delete:
        ok = delete_enrolled_profile(args.delete, store)
        if ok:
            print(f"✓ Successfully deleted voice profile for '{args.delete}'.")
        else:
            print(f"❌ Failed to delete voice profile for '{args.delete}'. Check that it exists.")
        return

    if args.from_wavs:
        if not args.user:
            print("❌ Error: --user <NAME> required when enrolling --from-wavs.")
            sys.exit(1)
        res = enroll_from_files(args.user, args.from_wavs, profile_store=store)
        if res.success:
            print(f"✓ Enrolled profile '{args.user}' with calibrated threshold {res.profile.threshold:.3f}")
        else:
            print(f"❌ Enrollment failed: {res.error_message}")
            sys.exit(1)
        return

    if args.enroll:
        ok = enroll_interactive(args.enroll, profile_store=store)
        sys.exit(0 if ok else 1)

    if args.benchmark:
        print("▶ Benchmarking CampplusOnnxExtractor latency...")
        ext = CampplusOnnxExtractor()
        sr = 16000
        dummy_audio = np.random.randn(int(1.5 * sr)).astype(np.float32)
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            ext.extract_embedding(dummy_audio, sr)
            times.append((time.perf_counter() - t0) * 1000)
        times = times[5:]  # drop warmup
        print(f"✓ Embedding extraction latency: median {np.median(times):.2f} ms (p95: {np.percentile(times, 95):.2f} ms)")
        return

    parser.print_help()


if __name__ == "__main__":
    main()

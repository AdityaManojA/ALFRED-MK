"""
Unit tests for Phase 2: Capability matrix, asset validation, and base model resolution.
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from core.tts.engine_base import Capability
from core.tts.capability import (
    check_jarvis_capability,
    check_python_version,
    JARVIS_MIN_VRAM_GB,
    JARVIS_REPO,
    JARVIS_REVISION,
)
from core.tts.jarvis_assets import (
    are_assets_downloaded,
    find_reference_audio,
)


class TestJarvisVoicePhase2Capability(unittest.TestCase):
    """Test full matrix of capability states."""

    def test_python_version_gating(self):
        """voxcpm requires Python >= 3.10 and < 3.13."""
        with patch.object(sys, "version_info", (3, 9, 7)):
            self.assertFalse(check_python_version())
            self.assertEqual(check_jarvis_capability(), Capability.PYTHON_VERSION)

        with patch.object(sys, "version_info", (3, 13, 0)):
            self.assertFalse(check_python_version())
            self.assertEqual(check_jarvis_capability(), Capability.PYTHON_VERSION)

        with patch.object(sys, "version_info", (3, 12, 5)):
            self.assertTrue(check_python_version())

    def test_missing_dependencies_state(self):
        """Missing optional dependencies must report MISSING_DEPS."""
        with patch("core.tts.capability.check_python_version", return_value=True):
            with patch("core.tts.capability.check_dependencies", return_value=False):
                self.assertEqual(check_jarvis_capability(), Capability.MISSING_DEPS)

    def test_no_cuda_vs_cpu_only_states(self):
        """No CUDA GPU reports NO_CUDA by default, and CPU_ONLY if allow_cpu=True."""
        with patch("core.tts.capability.check_python_version", return_value=True):
            with patch("core.tts.capability.check_dependencies", return_value=True):
                with patch("core.tts.capability.check_cuda_and_vram", return_value=(False, False, 0.0)):
                    # Default: CPU inference disallowed
                    self.assertEqual(check_jarvis_capability(allow_cpu=False), Capability.NO_CUDA)

                    # When allow_cpu is enabled, assets downloaded check is evaluated
                    with patch("core.tts.jarvis_assets.are_assets_downloaded", return_value=True):
                        self.assertEqual(check_jarvis_capability(allow_cpu=True), Capability.CPU_ONLY)

    def test_low_vram_state(self):
        """CUDA GPU with < 8 GB VRAM reports LOW_VRAM."""
        with patch("core.tts.capability.check_python_version", return_value=True):
            with patch("core.tts.capability.check_dependencies", return_value=True):
                # CUDA present, but only 4 GB VRAM
                with patch("core.tts.capability.check_cuda_and_vram", return_value=(True, False, 4.0)):
                    self.assertEqual(check_jarvis_capability(), Capability.LOW_VRAM)

    def test_not_downloaded_state(self):
        """CUDA and dependencies OK, but assets missing reports NOT_DOWNLOADED."""
        with patch("core.tts.capability.check_python_version", return_value=True):
            with patch("core.tts.capability.check_dependencies", return_value=True):
                with patch("core.tts.capability.check_cuda_and_vram", return_value=(True, True, 16.0)):
                    with patch("core.tts.jarvis_assets.are_assets_downloaded", return_value=False):
                        self.assertEqual(check_jarvis_capability(), Capability.NOT_DOWNLOADED)

    def test_capability_ok_state(self):
        """All checks passing reports OK."""
        with patch("core.tts.capability.check_python_version", return_value=True):
            with patch("core.tts.capability.check_dependencies", return_value=True):
                with patch("core.tts.capability.check_cuda_and_vram", return_value=(True, True, 16.0)):
                    with patch("core.tts.jarvis_assets.are_assets_downloaded", return_value=True):
                        self.assertEqual(check_jarvis_capability(), Capability.OK)


class TestJarvisVoicePhase2Assets(unittest.TestCase):
    """Test asset management, base model resolution, and file validation."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.asset_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_constants_pinned(self):
        """Verify repository and revision constants match ground rules."""
        self.assertEqual(JARVIS_REPO, "FuturePresentLabs/tts-jarvis")
        self.assertEqual(JARVIS_REVISION, "v4-interface-2026-09-06")
        self.assertEqual(JARVIS_MIN_VRAM_GB, 8.0)

    def test_asset_detection_on_empty_dir(self):
        """Empty directory must report assets not downloaded."""
        with patch("core.tts.jarvis_assets.get_jarvis_asset_dir", return_value=self.asset_dir):
            self.assertFalse(are_assets_downloaded())

    def test_asset_detection_with_valid_files(self):
        """Valid directory structure with reference audio must report downloaded."""
        adapter_dir = self.asset_dir / "adapter"
        adapter_dir.mkdir(parents=True)
        (adapter_dir / "inference_config.json").write_text(json.dumps({
            "base_model": "openbmb/VoxCPM2",
            "base_revision": "32279effe8c19989596f05d353d1447f51d9e915"
        }))
        (adapter_dir / "lora_config.json").write_text(json.dumps({"lora_config": {}}))
        (adapter_dir / "reference.wav").write_bytes(b"RIFFdummydata")

        base_dir = self.asset_dir / "base"
        base_dir.mkdir(parents=True)
        (base_dir / "model.safetensors").write_bytes(b"dummy_weights")

        with patch("core.tts.jarvis_assets.get_jarvis_asset_dir", return_value=self.asset_dir):
            self.assertTrue(are_assets_downloaded())


if __name__ == "__main__":
    unittest.main()

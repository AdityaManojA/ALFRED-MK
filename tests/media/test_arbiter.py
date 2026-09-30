import unittest
from core.media.arbiter import AudioSource, MediaArbiter


class _FakeSuppressor:
    def __init__(self):
        self.handles = ["external-player"]
        self.paused = []
        self.playing = {"external-player": True}

    def enumerate_players(self):
        return list(self.handles)

    def pause(self, handle):
        self.paused.append(handle)
        self.playing[handle] = False
        return True

    def resume(self, handle):
        self.playing[handle] = True
        return True

    def is_playing(self, handle):
        return self.playing[handle]


class TestMediaArbiter(unittest.TestCase):
    def test_claim_release_and_tts_duck_state(self):
        arbiter = MediaArbiter()

        self.assertFalse(arbiter.state.app_playing)
        arbiter.claim(AudioSource.APP_PLAYER)
        self.assertTrue(arbiter.state.app_playing)
        self.assertFalse(arbiter.state.tts_ducking)

        arbiter.claim(AudioSource.TTS)
        self.assertTrue(arbiter.state.tts_ducking)

        arbiter.release(AudioSource.TTS)
        self.assertFalse(arbiter.state.tts_ducking)
        arbiter.release(AudioSource.APP_PLAYER)
        self.assertFalse(arbiter.state.app_playing)

    def test_app_player_claim_suppresses_external_player(self):
        suppressor = _FakeSuppressor()
        arbiter = MediaArbiter(suppressor=suppressor)
        arbiter.claim(AudioSource.APP_PLAYER)

        import time
        deadline = time.monotonic() + 1.0
        while not suppressor.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(suppressor.paused, ["external-player"])
        self.assertTrue(arbiter.state.external_suppressed)
        self.assertEqual(arbiter.state.suppressed_count, 1)

    def test_app_player_release_resumes_external_player(self):
        suppressor = _FakeSuppressor()
        arbiter = MediaArbiter(suppressor=suppressor)
        arbiter.claim(AudioSource.APP_PLAYER)

        import time
        deadline = time.monotonic() + 1.0
        while not suppressor.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(suppressor.is_playing("external-player"))

        # Release APP_PLAYER: with RESUME_EXTERNAL_ON_STOP=True, it resumes!
        arbiter.release(AudioSource.APP_PLAYER)
        self.assertTrue(suppressor.is_playing("external-player"))
        self.assertFalse(arbiter.state.app_playing)


if __name__ == "__main__":
    unittest.main()


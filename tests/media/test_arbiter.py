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


def test_claim_release_and_tts_duck_state():
    arbiter = MediaArbiter()

    assert not arbiter.state.app_playing
    arbiter.claim(AudioSource.APP_PLAYER)
    assert arbiter.state.app_playing
    assert not arbiter.state.tts_ducking

    arbiter.claim(AudioSource.TTS)
    assert arbiter.state.tts_ducking

    arbiter.release(AudioSource.TTS)
    assert not arbiter.state.tts_ducking
    arbiter.release(AudioSource.APP_PLAYER)
    assert not arbiter.state.app_playing


def test_app_player_claim_suppresses_external_player():
    suppressor = _FakeSuppressor()
    arbiter = MediaArbiter(suppressor=suppressor)
    arbiter.claim(AudioSource.APP_PLAYER)

    # The watchdog sweeps immediately, but this assertion remains event-loop independent.
    import time
    deadline = time.monotonic() + 1.0
    while not suppressor.paused and time.monotonic() < deadline:
        time.sleep(0.01)
    assert suppressor.paused == ["external-player"]
    assert arbiter.state.external_suppressed
    assert arbiter.state.suppressed_count == 1

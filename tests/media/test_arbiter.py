from core.media.arbiter import AudioSource, MediaArbiter


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

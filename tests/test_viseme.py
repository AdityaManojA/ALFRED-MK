"""Behavioural tests for core.viseme (text -> mouth shape fusion)."""
import pytest

import core.viseme as viseme
from core.viseme import VISEMES, VisemeStream, coverage, text_to_visemes, to_latin


@pytest.mark.parametrize(
    "ch, expected",
    [
        ("A", "a"),
        ("z", "z"),
        ("é", "e"),
        ("ü", "u"),
        ("ş", "s"),
        ("ñ", "n"),
        ("ı", "i"),      # Turkish dotless i (no decomposition)
        ("ß", "s"),
        ("ł", "l"),
        ("б", "b"),      # Cyrillic
        ("Ж", "j"),      # Cyrillic uppercase
        ("ь", ""),       # soft sign maps to nothing
        ("λ", "l"),      # Greek
        ("ω", "o"),
        pytest.param(
            "ﬁ", "f",
            marks=pytest.mark.xfail(
                reason="to_latin uses NFD, which does not decompose compatibility "
                       "ligatures; the in-code comment 'ﬁ → fi' is not honoured",
                strict=True,
            ),
        ),
        ("1", ""),
        ("中", ""),
        (" ", ""),
    ],
)
def test_to_latin_reduction(ch, expected):
    assert to_latin(ch) == expected


def test_coverage_counts_only_letters():
    assert coverage("") == 0.0
    assert coverage(None) == 0.0
    assert coverage("123 !!") == 0.0
    assert coverage("hello") == 1.0
    assert coverage("ab中中") == pytest.approx(0.5)


def test_text_to_visemes_skips_unreadable_scripts():
    assert text_to_visemes("你好世界") == []
    assert text_to_visemes("") == []


def test_text_to_visemes_basic_letters_and_durations():
    out = text_to_visemes("mama")
    # m->MBP, a->AA alternating; durations come from _DUR
    assert [v for v, _ in out] == ["MBP", "AA", "MBP", "AA"]
    assert out[0][1] == viseme._DUR["MBP"]
    assert out[1][1] == viseme._DUR["AA"]


def test_text_to_visemes_collapses_doubled_letters():
    assert [v for v, _ in text_to_visemes("ll")] == ["L"]
    assert [v for v, _ in text_to_visemes("mmmb")] == ["MBP"]


def test_text_to_visemes_digraphs():
    # "sh" -> S as one unit, "th" -> TD, "ph" -> FV
    assert [v for v, _ in text_to_visemes("sha")] == ["S", "AA"]
    assert [v for v, _ in text_to_visemes("tha")] == ["TD", "AA"]
    assert [v for v, _ in text_to_visemes("pha")] == ["FV", "AA"]
    # Digraph matching works on reduced letters (uppercase input lowered)
    assert [v for v, _ in text_to_visemes("SHA")] == ["S", "AA"]


def test_text_to_visemes_pause_and_word_gap():
    out = text_to_visemes("ma, ma")
    names = [v for v, _ in out]
    assert names == ["MBP", "AA", "REST", "MBP", "AA"]
    rest = out[2]
    assert rest == ("REST", 1.4)

    # A word gap repeats the previous shape with a short beat
    out = text_to_visemes("a b")
    assert out[1] == ("AA", 0.35)
    assert out[2][0] == "MBP"


def test_text_to_visemes_cyrillic_and_greek():
    assert [v for v, _ in text_to_visemes("мама")] == ["MBP", "AA", "MBP", "AA"]
    assert [v for v, _ in text_to_visemes("λα")] == ["L", "AA"]


def test_stream_feed_and_reset():
    s = VisemeStream()
    s.feed_text("mama")
    assert s.pending == 4
    s.reset()
    assert s.pending == 0
    assert s._cur == ("REST", 1.0)
    assert s._carry == 0.0


def test_stream_feed_caps_backlog():
    s = VisemeStream()
    s.feed_text("ba " * 400)
    assert s.pending == 600


def test_step_seconds_shrinks_with_backlog():
    s = VisemeStream()
    assert s._step_seconds() == pytest.approx(VisemeStream._MAX_STEP)
    s.feed_text("ba " * 100)  # > 45 entries -> fully saturated backlog
    assert s._step_seconds() == pytest.approx(VisemeStream._MIN_STEP)


def test_frames_silence_does_not_consume_queue():
    s = VisemeStream()
    s.feed_text("mama")
    out = s.frames([(0.0, 0.5, 0.5), (-1.0, 0.2, 0.2)], hop=0.5)
    assert out == [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    assert s.pending == 4


def test_frames_audio_only_when_queue_empty():
    s = VisemeStream()
    out = s.frames([(0.8, 0.6, -0.3)], hop=0.01)
    assert out == [(0.8, 0.6, -0.3)]


def test_frames_closure_shuts_mouth_for_mbp():
    s = VisemeStream()
    s.feed_text("m")
    # Large hop advances the clock so the MBP shape is popped.
    out = s.frames([(1.0, 0.9, 0.5)], hop=1.0)
    level, openness, width = out[0]
    assert level == 1.0
    assert openness == 0.0  # closure=1 forces the lips together
    assert width == pytest.approx(0.78 * VISEMES["MBP"][1] + 0.22 * 0.5)
    assert s.pending == 0


def test_frames_blend_vowel_and_clamp():
    s = VisemeStream()
    s.feed_text("a")
    out = s.frames([(0.5, 1.0, -1.0)], hop=1.0)
    t_open, t_wide, _ = VISEMES["AA"]
    _, o, w = out[0]
    assert o == pytest.approx(0.72 * t_open + 0.28 * 1.0)
    assert w == pytest.approx(0.78 * t_wide + 0.22 * -1.0)
    assert 0.0 <= o <= 1.0 and -1.0 <= w <= 1.0


def test_frames_carry_clamped_when_queue_empty():
    s = VisemeStream()
    s.feed_text("a")
    s.frames([(0.5, 0.1, 0.1)], hop=10.0)
    assert s._carry == 1.0
    assert s._cur[0] == "AA"

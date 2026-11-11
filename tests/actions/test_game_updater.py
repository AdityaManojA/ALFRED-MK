"""Behavioural tests for actions.game_updater.

Steam libraries are built as fake .acf/.vdf files under tmp_path; the OS is
forced to Linux via the module's is_* helpers; subprocess, urllib, threads and
time.sleep are mocked so nothing is launched or downloaded.
"""
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.game_updater as gu
from actions.game_updater import game_updater


@pytest.fixture(autouse=True)
def _linux_no_sleep(monkeypatch):
    monkeypatch.setattr(gu, "is_windows", lambda: False)
    monkeypatch.setattr(gu, "is_mac", lambda: False)
    monkeypatch.setattr(gu, "is_linux", lambda: True)
    monkeypatch.setattr(gu.time, "sleep", lambda *_: None)


def _acf(lib: Path, app_id: str, name: str, state: int = 4, size: int = 1000) -> Path:
    lib.mkdir(parents=True, exist_ok=True)
    p = lib / f"appmanifest_{app_id}.acf"
    p.write_text(
        '"AppState"\n{\n'
        f'\t"appid"\t\t"{app_id}"\n'
        f'\t"name"\t\t"{name}"\n'
        f'\t"StateFlags"\t\t"{state}"\n'
        f'\t"SizeOnDisk"\t\t"{size}"\n'
        "}\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def steam(tmp_path):
    root = tmp_path / "Steam"
    (root / "steamapps").mkdir(parents=True)
    return root


# ── library / manifest parsing ───────────────────────────────────────────────

def test_libraries_include_extra_paths_from_vdf(steam, tmp_path):
    extra = tmp_path / "Games"
    (extra / "steamapps").mkdir(parents=True)
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    vdf.write_text(
        '"libraryfolders"\n{\n "0" { "path" "%s" }\n "1" { "path" "%s" }\n "2" { "path" "/does/not/exist" }\n}'
        % (str(steam).replace("\\", "\\\\"), str(extra).replace("\\", "\\\\")),
        encoding="utf-8",
    )
    libs = gu._get_steam_libraries(steam)
    assert libs[0] == steam / "steamapps"
    assert extra / "steamapps" in libs
    assert len(libs) == 2  # default + extra; duplicate and missing ignored


def test_get_steam_games_parses_manifests(steam):
    _acf(steam / "steamapps", "730", "Counter-Strike 2", state=4, size=42)
    _acf(steam / "steamapps", "570", "Dota 2", state=1026)
    (steam / "steamapps" / "appmanifest_bad.acf").write_text("garbage", encoding="utf-8")
    games = {g["id"]: g for g in gu._get_steam_games(steam)}
    assert set(games) == {"730", "570"}
    assert games["730"]["name"] == "Counter-Strike 2"
    assert games["730"]["state"] == 4 and games["730"]["size"] == 42
    assert games["570"]["state"] == 1026


def test_steam_exe_per_platform(monkeypatch, steam):
    assert gu._steam_exe(steam) == steam / "steam.sh"
    monkeypatch.setattr(gu, "is_windows", lambda: True)
    assert gu._steam_exe(steam) == steam / "steam.exe"


def test_launch_steam_url_uses_xdg_open_on_linux():
    with patch.object(gu.subprocess, "Popen") as popen:
        gu._launch_steam_url(Path("steam.sh"), "steam://update/1")
    popen.assert_called_once_with(["xdg-open", "steam://update/1"])


# ── AppID lookup ─────────────────────────────────────────────────────────────

def test_search_appid_prefers_installed_game(steam):
    _acf(steam / "steamapps", "999", "My Indie Game")
    with patch.object(gu, "_find_steam_path", return_value=steam):
        assert gu._search_steam_appid("indie") == ("999", "My Indie Game")


def test_search_appid_known_exact_and_partial():
    with patch.object(gu, "_find_steam_path", return_value=None):
        assert gu._search_steam_appid("PUBG") == ("578080", "PUBG: Battlegrounds")
        assert gu._search_steam_appid("elden") == ("1245620", "ELDEN RING")


def test_search_appid_store_api_fallback():
    body = json.dumps({"items": [{"id": 12345, "name": "Obscure Game"}]}).encode()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch.object(gu, "_find_steam_path", return_value=None), \
         patch("urllib.request.urlopen", return_value=_Resp(body)) as urlopen:
        assert gu._search_steam_appid("zzqx obscure") == ("12345", "Obscure Game")
    assert "term=zzqx%20obscure" in urlopen.call_args.args[0].full_url


def test_search_appid_store_api_failure():
    with patch.object(gu, "_find_steam_path", return_value=None), \
         patch("urllib.request.urlopen", side_effect=OSError("offline")):
        assert gu._search_steam_appid("zzqx obscure") == (None, None)


# ── update / install flows ───────────────────────────────────────────────────

def test_update_steam_games_classifies_by_state(steam):
    lib = steam / "steamapps"
    _acf(lib, "1", "Alpha", state=4)
    _acf(lib, "2", "Beta", state=1026)
    _acf(lib, "3", "Gamma", state=6)
    with patch.object(gu, "_ensure_steam_running", return_value=True), \
         patch.object(gu, "_launch_steam_url") as launch:
        out = gu._update_steam_games(steam)
    launch.assert_called_once_with(steam / "steam.sh", "steam://update/3")
    assert "Update started for: Gamma." in out
    assert "Already updating: Beta." in out
    assert "1 game(s) already up to date." in out


def test_update_steam_games_unknown_name_lists_installed(steam):
    _acf(steam / "steamapps", "1", "Alpha")
    with patch.object(gu, "_ensure_steam_running", return_value=True):
        out = gu._update_steam_games(steam, game_name="zelda")
    assert out == "Game 'zelda' not found. Installed: Alpha..."


def test_update_steam_games_when_steam_wont_start(steam):
    with patch.object(gu, "_ensure_steam_running", return_value=False):
        assert gu._update_steam_games(steam) == "Could not start Steam."


@pytest.mark.parametrize(
    "state, expected",
    [
        (4, "'Alpha' is already installed and up to date."),
        (1026, "'Alpha' is currently downloading or updating."),
        (6, "'Alpha' has a pending update. Update started."),
        (2, "'Alpha' is already installed."),
    ],
)
def test_install_existing_game_by_state(steam, state, expected):
    _acf(steam / "steamapps", "1", "Alpha", state=state)
    with patch.object(gu, "_ensure_steam_running", return_value=True), \
         patch.object(gu, "_launch_steam_url"):
        assert gu._install_steam_game(steam, game_name="alpha") == expected


def test_install_new_game_resolves_appid_and_launches(steam):
    with patch.object(gu, "_ensure_steam_running", return_value=True), \
         patch.object(gu, "_search_steam_appid", return_value=("252490", "Rust")), \
         patch.object(gu, "_launch_steam_url") as launch:
        out = gu._install_steam_game(steam, game_name="rust")
    launch.assert_called_once_with(steam / "steam.sh", "steam://install/252490")
    assert out == "Install started for 'Rust'. Steam will open the download dialog."


def test_install_unknown_game(steam):
    with patch.object(gu, "_ensure_steam_running", return_value=True), \
         patch.object(gu, "_search_steam_appid", return_value=(None, None)):
        out = gu._install_steam_game(steam, game_name="nothing")
    assert out.startswith("Could not find 'nothing' on Steam.")


def test_install_requires_name_or_id(steam):
    with patch.object(gu, "_ensure_steam_running", return_value=True):
        assert gu._install_steam_game(steam) == "Please specify a game name or AppID."


def test_download_status(steam):
    lib = steam / "steamapps"
    assert gu._get_download_status(steam) == "No active downloads or pending updates."
    _acf(lib, "1", "Alpha", state=1026)
    _acf(lib, "2", "Beta", state=516)
    out = gu._get_download_status(steam)
    assert out == "Downloading: Alpha. Pending updates: Beta."


def test_ensure_steam_running_short_circuits(steam):
    with patch.object(gu, "_is_steam_running", return_value=True), \
         patch.object(gu.subprocess, "Popen") as popen:
        assert gu._ensure_steam_running(steam) is True
    popen.assert_not_called()


def test_ensure_steam_running_missing_exe(steam):
    with patch.object(gu, "_is_steam_running", return_value=False):
        assert gu._ensure_steam_running(steam) is False


# ── Epic ─────────────────────────────────────────────────────────────────────

def test_get_epic_games_reads_item_manifests(tmp_path):
    (tmp_path / "a.item").write_text(json.dumps({"DisplayName": "Fortnite", "AppName": "Fn"}), encoding="utf-8")
    (tmp_path / "b.item").write_text(json.dumps({"AppName": "OnlyId"}), encoding="utf-8")
    (tmp_path / "c.item").write_text("not json", encoding="utf-8")
    with patch.object(gu, "_epic_manifests_path", return_value=tmp_path):
        games = sorted(gu._get_epic_games(), key=lambda g: g["name"])
    assert games == [{"id": "Fn", "name": "Fortnite"}, {"id": "OnlyId", "name": "OnlyId"}]


def test_update_epic_game_not_found():
    with patch.object(gu, "_get_epic_games", return_value=[]):
        assert gu._update_epic_games(Path("heroic"), "zelda") == "'zelda' not found in Epic."


# ── scheduling (Linux / cron path) ───────────────────────────────────────────

def test_schedule_linux_replaces_existing_entry():
    marker_line = "0 4 * * * python x --scheduled  # ALFRED_GameUpdater"
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        if cmd == ["crontab", "-l"]:
            return SimpleNamespace(stdout=f"5 5 * * * backup\n{marker_line}\n", returncode=0)
        return SimpleNamespace(returncode=0, stderr="")

    with patch.object(gu.subprocess, "run", side_effect=fake_run):
        out = gu._schedule_linux(7, 5)
    assert out == "Daily game update scheduled at 07:05 via cron."
    new_tab = calls[-1][1]["input"].splitlines()
    assert new_tab[0] == "5 5 * * * backup"
    assert len(new_tab) == 2 and new_tab[1].startswith("5 7 * * * ")
    assert new_tab[1].endswith("# ALFRED_GameUpdater")


def test_schedule_status_linux():
    tab = SimpleNamespace(stdout="0 3 * * * py s --scheduled  # ALFRED_GameUpdater\n")
    with patch.object(gu.subprocess, "run", return_value=tab):
        assert gu._get_schedule_status() == "Game update is scheduled: 0 3 * * * py s --scheduled"
    with patch.object(gu.subprocess, "run", return_value=SimpleNamespace(stdout="")):
        assert gu._get_schedule_status() == "No scheduled game update found."


def test_cancel_schedule_linux_filters_markers():
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return SimpleNamespace(stdout="keep me\nx # JARVIS_GameUpdater\ny # ALFRED_GameUpdater\n")

    with patch.object(gu.subprocess, "run", side_effect=fake_run):
        assert gu._cancel_scheduled_update() == "Scheduled update cancelled."
    assert calls[-1][1]["input"] == "keep me\n"


# ── game_updater dispatch ────────────────────────────────────────────────────

def test_dispatch_unknown_action():
    assert game_updater({"action": "fly"}) == "Unknown action: 'fly'."


def test_dispatch_list_steam_and_epic_on_linux(steam):
    for i in range(10):
        _acf(steam / "steamapps", str(i), f"Game{i}")
    with patch.object(gu, "_find_steam_path", return_value=steam):
        out = game_updater({"action": "list"})
    steam_part, epic_part = out.split(" | ")
    assert steam_part.startswith("Steam (10 games): ")
    assert steam_part.endswith(" and 2 more.")
    assert epic_part == "Epic: Not natively supported on Linux."


def test_dispatch_steam_not_installed():
    with patch.object(gu, "_find_steam_path", return_value=None):
        assert game_updater({"action": "update", "platform": "steam"}) == "Steam: Not installed."


def test_dispatch_install_without_name(steam):
    with patch.object(gu, "_find_steam_path", return_value=steam):
        out = game_updater({"action": "install", "platform": "steam"})
    assert out == "Steam: Please specify a game name to install."


def test_dispatch_install_uninstalled_game_with_shutdown_watch(steam):
    player, speak = MagicMock(), MagicMock()
    with patch.object(gu, "_find_steam_path", return_value=steam), \
         patch.object(gu, "_install_steam_game", return_value="Install started.") as inst, \
         patch.object(gu.threading, "Thread") as thread:
        out = game_updater(
            {"action": "install", "platform": "steam", "game_name": "Rust",
             "shutdown_when_done": "true"},
            player=player, speak=speak,
        )
    assert out == "Install started. Auto-shutdown enabled."
    inst.assert_called_once_with(steam, game_name="Rust", app_id=None)
    thread.return_value.start.assert_called_once()
    speak.assert_called_once_with(out)


def test_dispatch_schedule_routes_hour_minute():
    with patch.object(gu, "_schedule_daily_update", return_value="ok") as sched:
        assert game_updater({"action": "schedule", "hour": "5", "minute": 30}) == "ok"
    sched.assert_called_once_with(hour=5, minute=30)

from types import SimpleNamespace

from ethergpt import service


def _fake_launchctl(monkeypatch, tmp_path, *, initially_loaded: bool):
    target = tmp_path / "Library" / "LaunchAgents" / "org.ethergpt.gateway.plist"
    target.parent.mkdir(parents=True)
    target.write_text("plist")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["launchctl", "print"]:
            return SimpleNamespace(returncode=0 if initially_loaded else 113)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.os, "getuid", lambda: 501)
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service.subprocess, "run", fake_run)
    return calls


def test_enable_bootstraps_once_without_forced_restart(monkeypatch, tmp_path) -> None:
    calls = _fake_launchctl(monkeypatch, tmp_path, initially_loaded=False)
    assert service.service_action("enable") == 0
    assert any(command[:2] == ["launchctl", "bootstrap"] for command in calls)
    assert not any("-k" in command for command in calls)
    assert not any(command[:2] == ["launchctl", "kickstart"] for command in calls)


def test_enable_does_not_kill_an_already_running_service(monkeypatch, tmp_path) -> None:
    calls = _fake_launchctl(monkeypatch, tmp_path, initially_loaded=True)
    assert service.service_action("enable") == 0
    kickstarts = [command for command in calls if command[:2] == ["launchctl", "kickstart"]]
    assert kickstarts == [["launchctl", "kickstart", "gui/501/org.ethergpt.gateway"]]


def test_restart_bootstraps_once(monkeypatch, tmp_path) -> None:
    calls = _fake_launchctl(monkeypatch, tmp_path, initially_loaded=True)
    assert service.service_action("restart") == 0
    assert sum(command[:2] == ["launchctl", "bootstrap"] for command in calls) == 1
    assert not any(command[:2] == ["launchctl", "kickstart"] for command in calls)

"""Tests for the self-update mechanism (flugradar/system/update.py).

All git/pip/systemctl calls go through `_run`, which is monkeypatched
here to a fake -- no real subprocess ever runs, so these are safe to
execute against the actual dev checkout.
"""

from unittest.mock import MagicMock, patch

import pytest

from flugradar.system import update as update_mod


def _cp(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class _FakeRun:
    """Scripted replacement for update._run: pop canned results off a
    dict keyed by the command's first two argv tokens (enough to
    distinguish `git fetch` from `git reset` etc. without over-matching)."""

    def __init__(self, responses: dict[tuple, MagicMock]):
        self.responses = responses
        self.calls: list[list[str]] = []

    def __call__(self, cmd, timeout=None):
        self.calls.append(cmd)
        key = tuple(cmd[:2])
        if key in self.responses:
            return self.responses[key]
        return _cp(0, "", "")


_CLEAN_STATUS = _cp(0, "", "")
_OLD_SHA = "aaaaaaaa1111111111111111111111111111aaaa"
_NEW_SHA = "bbbbbbbb2222222222222222222222222222bbbb"


def _base_responses(**overrides):
    responses = {
        ("git", "fetch"): _cp(0),
        ("git", "status"): _CLEAN_STATUS,
        ("git", "reset"): _cp(0),
        ("sudo", "systemctl"): _cp(0),
    }
    responses.update(overrides)
    return responses


class TestUpToDate:
    def test_same_sha_is_a_noop(self):
        fake = _FakeRun(_base_responses())
        # rev-parse HEAD and rev-parse origin/main both return the same sha
        with patch.object(update_mod, "_run", side_effect=self._rev_parse_same):
            result = update_mod.apply_update()
        assert result.ok is True
        assert "bereits aktuell" in result.message

    @staticmethod
    def _rev_parse_same(cmd, timeout=None):
        if cmd[:2] == ["git", "rev-parse"]:
            return _cp(0, _OLD_SHA + "\n")
        if cmd[:2] == ["git", "status"]:
            return _CLEAN_STATUS
        return _cp(0)


class TestDirtyWorkingTree:
    def test_refuses_when_local_changes_present(self):
        def fake(cmd, timeout=None):
            if cmd[:2] == ["git", "status"]:
                return _cp(0, " M some_file.py\n")
            return _cp(0)

        with patch.object(update_mod, "_run", side_effect=fake):
            result = update_mod.apply_update()
        assert result.ok is False
        assert "lokale Änderungen" in result.message


class TestFetchFailure:
    def test_fetch_error_is_reported_not_raised(self):
        def fake(cmd, timeout=None):
            if cmd[:2] == ["git", "fetch"]:
                return _cp(1, "", "network unreachable")
            return _cp(0)

        with patch.object(update_mod, "_run", side_effect=fake):
            result = update_mod.apply_update()
        assert result.ok is False
        assert "Abruf fehlgeschlagen" in result.message


def _rev_parse(sha_for_head: str, sha_for_remote: str):
    def fake(cmd, timeout=None):
        if cmd[:2] == ["git", "rev-parse"] and cmd[-1] == "HEAD":
            return _cp(0, sha_for_head + "\n")
        if cmd[:2] == ["git", "rev-parse"] and cmd[-1] == "origin/main":
            return _cp(0, sha_for_remote + "\n")
        return None
    return fake


class TestSuccessfulUpdate:
    def test_happy_path_restarts_web_then_display(self):
        calls: list[list[str]] = []

        def fake(cmd, timeout=None):
            calls.append(cmd)
            rp = _rev_parse(_OLD_SHA, _NEW_SHA)(cmd, timeout)
            if rp is not None:
                return rp
            if cmd[:2] == ["git", "status"]:
                return _CLEAN_STATUS
            return _cp(0)

        with patch.object(update_mod, "_run", side_effect=fake):
            result = update_mod.apply_update()

        assert result.ok is True
        assert _OLD_SHA[:8] in result.message
        assert _NEW_SHA[:8] in result.message

        restart_calls = [c for c in calls if c[:2] == ["sudo", "systemctl"]]
        assert len(restart_calls) == 2
        assert "flugradar-web.service" in restart_calls[0]
        assert "flugradar-display.service" in restart_calls[1]
        # web must be restarted before display (self-referential restart last)
        web_idx = calls.index(restart_calls[0])
        display_idx = calls.index(restart_calls[1])
        assert web_idx < display_idx

    def test_resets_hard_to_origin_main(self):
        def fake(cmd, timeout=None):
            rp = _rev_parse(_OLD_SHA, _NEW_SHA)(cmd, timeout)
            if rp is not None:
                return rp
            if cmd[:2] == ["git", "status"]:
                return _CLEAN_STATUS
            return _cp(0)

        with patch.object(update_mod, "_run", side_effect=fake) as mock_run:
            update_mod.apply_update()

        reset_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][:2] == ["git", "reset"]]
        assert reset_calls == [["git", "reset", "--hard", "origin/main"]]


class TestPipFailureRollsBack:
    def test_pip_failure_rolls_back_and_does_not_restart(self):
        calls: list[list[str]] = []

        def fake(cmd, timeout=None):
            calls.append(cmd)
            rp = _rev_parse(_OLD_SHA, _NEW_SHA)(cmd, timeout)
            if rp is not None:
                return rp
            if cmd[:2] == ["git", "status"]:
                return _CLEAN_STATUS
            if "pip" in cmd:
                return _cp(1, "", "could not resolve dependency")
            return _cp(0)

        with patch.object(update_mod, "_run", side_effect=fake):
            result = update_mod.apply_update()

        assert result.ok is False
        assert "zurückgesetzt" in result.message
        assert _OLD_SHA[:8] in result.message
        rollback_calls = [c for c in calls if c[:3] == ["git", "reset", "--hard"] and c[-1] == _OLD_SHA]
        assert len(rollback_calls) == 1
        assert not any(c[:2] == ["sudo", "systemctl"] for c in calls)


class TestSanityCheckFailureRollsBack:
    def test_import_failure_rolls_back_and_does_not_restart(self):
        calls: list[list[str]] = []

        def fake(cmd, timeout=None):
            calls.append(cmd)
            rp = _rev_parse(_OLD_SHA, _NEW_SHA)(cmd, timeout)
            if rp is not None:
                return rp
            if cmd[:2] == ["git", "status"]:
                return _CLEAN_STATUS
            if "-c" in cmd:  # the `python -c "import ..."` sanity check
                return _cp(1, "", "ModuleNotFoundError: no module named 'foo'")
            return _cp(0)

        with patch.object(update_mod, "_run", side_effect=fake):
            result = update_mod.apply_update()

        assert result.ok is False
        assert "ließ sich nicht importieren" in result.message
        assert "zurückgesetzt" in result.message
        assert not any(c[:2] == ["sudo", "systemctl"] for c in calls)


class TestTriggerUpdateAsync:
    def test_spawns_a_detached_background_process(self, tmp_path, monkeypatch):
        monkeypatch.setattr(update_mod, "LOG_FILE", tmp_path / "update.log")
        with patch.object(update_mod.subprocess, "Popen") as mock_popen:
            update_mod.trigger_update_async()
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert "flugradar.system.update" in args[0]
        assert kwargs.get("start_new_session") is True

    def test_never_raises_even_if_popen_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(update_mod, "LOG_FILE", tmp_path / "update.log")
        with patch.object(update_mod.subprocess, "Popen", side_effect=OSError("nope")):
            update_mod.trigger_update_async()  # must not raise


class TestRunAndLog:
    def test_writes_result_to_log_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(update_mod, "LOG_FILE", tmp_path / "update.log")
        with patch.object(
            update_mod, "apply_update",
            return_value=update_mod.UpdateResult(True, "bereits aktuell"),
        ):
            update_mod.run_and_log()
        content = (tmp_path / "update.log").read_text()
        assert "OK" in content
        assert "bereits aktuell" in content

    def test_unexpected_exception_is_caught_and_logged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(update_mod, "LOG_FILE", tmp_path / "update.log")
        with patch.object(update_mod, "apply_update", side_effect=RuntimeError("boom")):
            update_mod.run_and_log()  # must not raise
        content = (tmp_path / "update.log").read_text()
        assert "FAILED" in content
        assert "boom" in content

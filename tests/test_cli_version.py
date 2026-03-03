from __future__ import annotations

import pytest

from renderscript import __version__, cli


def test_cli_global_version_flag_prints_version(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr("sys.argv", ["renderscript", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out == f"RenderScript AI v{__version__}"


def test_cli_version_subcommand_prints_version(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr("sys.argv", ["renderscript", "version"])
    assert cli.main() == 0
    out = capsys.readouterr().out.strip()
    assert out == f"RenderScript AI v{__version__}"

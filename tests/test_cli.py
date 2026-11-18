from vscode_autoapprove.cli import main


def test_install_and_remove_logon_startup_through_the_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    script = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "vscode-autoapprove.vbs"

    assert main(["install-startup"]) == 0
    assert script.exists()
    assert main(["uninstall-startup"]) == 0
    assert not script.exists()

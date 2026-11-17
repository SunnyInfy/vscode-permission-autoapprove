from vscode_autoapprove.startup import build_vbs


def test_vbs_launcher_runs_pythonw_hidden_with_escaped_quotes(tmp_path):
    python_exe = tmp_path / "python.exe"
    python_exe.write_text("", encoding="utf-8")
    (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")
    config_path = tmp_path / "my config.json"

    script = build_vbs(str(python_exe), config_path)

    assert f'""{tmp_path / "pythonw.exe"}""' in script
    assert "-m vscode_autoapprove run" in script
    assert f'--config ""{config_path}""' in script
    assert script.rstrip().endswith("0, False")  # window style 0 = hidden

from vscode_autoapprove.logger import ActivityLogger


def test_record_appends_json_lines_and_recent_reads_them_back(tmp_path):
    log = ActivityLogger(tmp_path / "nested" / "activity.jsonl")

    log.record(outcome="clicked", app="Code.exe", window_title="w", dialog_text="Trust\n the authors?",
               button="Yes", source="uia", reason="approved")
    log.record(outcome="dry_run", app="Code.exe", window_title="w", dialog_text="x",
               button="OK", source="ocr")

    entries = log.recent(10)
    assert [e["outcome"] for e in entries] == ["clicked", "dry_run"]
    assert entries[0]["dialog_text"] == "Trust the authors?"
    assert entries[0]["timestamp"]

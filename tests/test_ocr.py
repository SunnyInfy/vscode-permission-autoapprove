from vscode_autoapprove.classifier import PermissionClassifier
from vscode_autoapprove.config import AppConfig
from vscode_autoapprove.ocr_fallback import OcrWord, build_snapshots, words_from_tesseract


def word(text, left, top, line, width=60, height=20, conf=90.0):
    return OcrWord(text, left, top, width, height, conf, line_key=(1, 1, line))


def test_words_from_tesseract_scales_and_drops_empty_or_negative_confidence():
    data = {
        "text": ["Allow", "", "junk"],
        "conf": ["95", "90", "-1"],
        "left": [20, 0, 0],
        "top": [40, 0, 0],
        "width": [80, 0, 0],
        "height": [30, 0, 0],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 2],
    }

    words = words_from_tesseract(data, scale=2)

    assert [w.text for w in words] == ["Allow"]
    assert (words[0].left, words[0].top, words[0].width) == (10, 20, 40)


def test_ocr_approves_button_in_dialog_row_and_ignores_distant_editor_text():
    classifier = PermissionClassifier(AppConfig())
    words = [
        word("Do", 100, 100, 1), word("you", 150, 100, 1), word("trust", 200, 100, 1),
        word("the", 260, 100, 1), word("authors?", 300, 100, 1),
        word("Yes,", 100, 200, 2), word("I", 170, 200, 2), word("trust", 200, 200, 2),
        word("the", 260, 200, 2), word("authors", 300, 200, 2),
        word("Cancel", 500, 202, 3),
        word("Remove", 100, 900, 4), word("item", 180, 900, 4),  # editor text far below the dialog
    ]

    snapshots = build_snapshots(
        words,
        approve_matcher=classifier.is_approve_label,
        min_confidence=60,
        origin=(1000, 500),
        app_name="Code.exe",
        title="w",
    )
    decisions = [classifier.classify(s) for s in snapshots]

    approved = [d for d in decisions if d.approve]
    assert approved and approved[0].button.label == "Yes, I trust the authors"
    assert approved[0].button.center == (1230, 710)  # line spans x 100-360, y 200-220 plus origin (1000, 500)
    assert all("Remove" not in s.dialog_text for s in snapshots)

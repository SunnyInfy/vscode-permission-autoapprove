import pytest

from vscode_autoapprove.classifier import PermissionClassifier, normalize_label
from vscode_autoapprove.config import AppConfig
from vscode_autoapprove.models import Button, DialogSnapshot


def snap(buttons, text="Do you want to continue?", native=False):
    return DialogSnapshot(
        app_name="Code.exe",
        window_title="project - Visual Studio Code",
        dialog_text=text,
        buttons=tuple(Button(label=b) for b in buttons),
        source="uia",
        is_native_dialog=native,
    )


@pytest.fixture
def classifier():
    return PermissionClassifier(AppConfig())


def test_picks_highest_priority_approve_label(classifier):
    decision = classifier.classify(snap(["Cancel", "Allow"]))

    assert decision.approve
    assert decision.button.label == "Allow"


def test_approves_workspace_trust_wording_and_ignores_restricted_mode(classifier):
    decision = classifier.classify(snap(["Yes, I trust the authors", "Restricted Mode"]))

    assert decision.approve
    assert decision.button.label == "Yes, I trust the authors"


@pytest.mark.parametrize("label", ["Don't Allow", "No, I don't trust the authors", "Continue in Restricted Mode"])
def test_negated_labels_are_never_approved(classifier, label):
    assert not classifier.is_approve_label(label)


def terminal(command, buttons=("Allow Once", "Skip", "Explain this command in a side chat")):
    return DialogSnapshot(
        app_name="Code.exe",
        window_title="w",
        dialog_text=command,
        buttons=tuple(Button(label=b) for b in buttons),
        source="uia",
        context_label="Chat Confirmation Dialog Run in terminal",
    )


def test_read_only_terminal_command_is_approved_with_skip_as_dismiss(classifier):
    command = (
        "cd story-factory; Import-Csv tracking\\stories.csv | Select-Object story_id,status "
        "| Format-Table -AutoSize | Out-String -Width 200"
    )

    decision = classifier.classify(terminal(command))

    assert decision.approve
    assert decision.button.label == "Allow Once"


@pytest.mark.parametrize(
    "command",
    [
        "Get-ChildItem | Remove-Item build -Recurse",
        "Get-Content notes.txt > copy.txt",
        "Get-Date; git push --force",
        "echo $(Remove-Item x)",
    ],
)
def test_terminal_commands_outside_the_read_only_allowlist_are_refused(classifier, command):
    decision = classifier.classify(terminal(command))

    assert not decision.approve


def test_destructive_text_blocks_approval_even_with_approve_button(classifier):
    decision = classifier.classify(snap(["Continue", "Cancel"], text="Delete the cache folder?"))

    assert not decision.approve
    assert "destructive" in decision.reason


def test_destructive_button_label_blocks_approval(classifier):
    decision = classifier.classify(snap(["Remove", "Allow", "Cancel"]))

    assert not decision.approve


def test_requires_dialog_context_unless_native(classifier):
    assert not classifier.classify(snap(["OK"])).approve
    assert classifier.classify(snap(["OK"], native=True)).approve


def test_label_normalization_strips_accelerators_and_ellipses():
    assert normalize_label("&Allow...") == "Allow"
    assert normalize_label("Don\u2019t  Allow") == "Don't Allow"

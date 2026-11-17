from vscode_autoapprove.config import AppConfig
from vscode_autoapprove.classifier import PermissionClassifier
from vscode_autoapprove.detector import UiaDialogDetector


class FakeElement:
    def __init__(self, control_type, parent=None):
        self.element_info = type("Info", (), {"control_type": control_type})()
        self._parent = parent

    def parent(self):
        return self._parent


def make_detector(context_depth=3):
    config = AppConfig(context_depth=context_depth)
    return UiaDialogDetector(config, PermissionClassifier(config))


def test_button_directly_under_top_level_window_uses_that_window_as_container():
    window = FakeElement("Window")
    button = FakeElement("Button", parent=window)

    container, is_dialog = make_detector()._find_container(button, window)

    assert container is window
    assert is_dialog is False


def test_nested_button_walks_up_to_enclosing_dialog():
    window = FakeElement("Window")
    dialog = FakeElement("Dialog", parent=window)
    group = FakeElement("Group", parent=dialog)
    button = FakeElement("Button", parent=group)

    container, is_dialog = make_detector()._find_container(button, window)

    assert container is dialog
    assert is_dialog is True

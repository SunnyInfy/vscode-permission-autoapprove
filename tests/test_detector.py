from types import SimpleNamespace

from vscode_autoapprove.config import AppConfig
from vscode_autoapprove.classifier import PermissionClassifier
from vscode_autoapprove.detector import UiaDialogDetector


class FakeElement:
    def __init__(self, control_type, name="", parent=None):
        self.element_info = SimpleNamespace(control_type=control_type)
        self._name = name
        self._parent = parent
        self._children = []
        if parent is not None:
            parent._children.append(self)

    def parent(self):
        return self._parent

    def window_text(self):
        return self._name

    def descendants(self, control_type=None):
        found, stack = [], list(self._children)
        while stack:
            element = stack.pop()
            found.append(element)
            stack.extend(element._children)
        return [e for e in found if control_type is None or e.element_info.control_type == control_type]


def make_detector(context_depth=3):
    config = AppConfig(context_depth=context_depth)
    return UiaDialogDetector(config, PermissionClassifier(config))


def test_button_directly_under_top_level_window_uses_that_window_as_container():
    window = FakeElement("Window")
    button = FakeElement("Button", "Allow", parent=window)

    container, is_dialog = make_detector()._find_container(button, window)

    assert container is window
    assert is_dialog is False


def test_nested_button_walks_up_to_enclosing_dialog():
    window = FakeElement("Window")
    dialog = FakeElement("Dialog", parent=window)
    group = FakeElement("Group", parent=dialog)
    button = FakeElement("Button", "Allow", parent=group)

    container, is_dialog = make_detector()._find_container(button, window)

    assert container is dialog
    assert is_dialog is True


def test_compact_group_is_chosen_over_large_ancestor_holding_the_whole_chat():
    window = FakeElement("Window")
    pane = FakeElement("Pane", parent=window)
    for index in range(30):  # unrelated chat content with buttons and text
        FakeElement("Button", f"Chat action {index}", parent=pane)
        FakeElement("Text", f"message {index}", parent=pane)
    group = FakeElement("Group", "Chat Confirmation Dialog Run in terminal", parent=pane)
    allow = FakeElement("Button", "Allow Once", parent=group)
    FakeElement("Button", "Skip", parent=group)
    FakeElement("Text", "cd story-factory; Get-ChildItem", parent=group)

    container, is_dialog = make_detector()._find_container(allow, window)

    assert container is group
    assert is_dialog is False


def test_button_inside_large_unbounded_area_is_ignored():
    window = FakeElement("Window")
    pane = FakeElement("Pane", parent=window)
    for index in range(30):
        FakeElement("Button", f"Chat action {index}", parent=pane)
    stray = FakeElement("Button", "OK", parent=pane)

    container, _ = make_detector()._find_container(stray, window)

    assert container is None

import os

from vscode_autoapprove.runtime import SingleInstanceLock, is_watcher_running


def test_lock_is_refused_while_the_owning_process_is_alive(tmp_path):
    lock_path = tmp_path / "run.lock"
    lock_path.write_text(str(os.getppid()), encoding="utf-8")  # parent process is certainly alive

    assert SingleInstanceLock(lock_path).acquire() is False
    assert is_watcher_running(lock_path)


def test_stale_lock_from_a_dead_process_is_replaced_and_released(tmp_path):
    lock_path = tmp_path / "run.lock"
    lock_path.write_text("999999", encoding="utf-8")  # no such process
    lock = SingleInstanceLock(lock_path)

    assert lock.acquire()
    assert not is_watcher_running(lock_path)  # our own pid never counts as "another watcher"
    lock.release()
    assert not lock_path.exists()

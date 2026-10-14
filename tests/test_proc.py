import subprocess
import time

import pytest
from ofd import proc


def test_stop_group_kills_children_too():
    # pai bash com filho em background que ignora SIGTERM: matar só o pai deixaria o filho órfão
    p = proc.spawn(["bash", "-c", "trap '' TERM; sleep 300 & wait"])
    time.sleep(0.5)
    kids = proc.group_pids(p)
    assert len(kids) >= 2
    proc.stop_group(p, grace_s=1.0)
    time.sleep(0.2)
    assert not any(proc.alive(pid) for pid in kids)


def test_refuses_when_pattern_running():
    p = subprocess.Popen(["sleep", "300"])
    try:
        with pytest.raises(RuntimeError, match="já em execução"):
            proc.assert_not_running("sleep 300")
    finally:
        p.kill(); p.wait()
    proc.assert_not_running("sleep 300")

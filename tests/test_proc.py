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


def test_refuses_only_for_exact_process_name(tmp_path):
    import shutil
    exe = tmp_path / "ofdtestnode"            # nome único (<= 15 chars, como fastlio_mapping)
    shutil.copy("/bin/sleep", exe)
    p = subprocess.Popen([str(exe), "300"])
    try:
        time.sleep(0.2)
        with pytest.raises(RuntimeError, match="já em execução"):
            proc.assert_not_running("ofdtestnode")
    finally:
        p.kill(); p.wait()
    proc.assert_not_running("ofdtestnode")


def test_command_lines_mentioning_the_name_do_not_count():
    # um shell cuja linha de comando só MENCIONA o nome não é o nó
    p = subprocess.Popen(["bash", "-c", "echo ofdtestnode >/dev/null; sleep 300"])
    try:
        time.sleep(0.2)
        proc.assert_not_running("ofdtestnode")
    finally:
        p.kill(); p.wait()

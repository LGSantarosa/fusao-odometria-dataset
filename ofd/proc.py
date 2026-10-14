"""Process-group lifecycle for ROS nodes: no orphans survive a run.

`ros2 launch` killed alone can leave its `fastlio_mapping` child orphaned; orphans keep subscribing and
publishing /Odometry under the same node name and silently contaminate later runs.
"""
import os
import signal
import subprocess
import time


def spawn(cmd, **kw):
    return subprocess.Popen(cmd, start_new_session=True, **kw)   # grupo próprio: dá para matar a árvore


def group_pids(p):
    r = subprocess.run(["pgrep", "-g", str(os.getpgid(p.pid))], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:   # zumbi ainda "existe" para kill(0)
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split()[2] != "Z"
    except FileNotFoundError:
        return False


def stop_group(p, grace_s=15.0):
    """SIGINT -> SIGTERM -> SIGKILL no grupo inteiro, esperando cada etapa."""
    try:
        pgid = os.getpgid(p.pid)
    except ProcessLookupError:
        return
    pids = group_pids(p)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            break
        t0 = time.time()
        while time.time() - t0 < grace_s and any(alive(x) for x in pids):
            time.sleep(0.2)
            p.poll()
        if not any(alive(x) for x in pids):
            break
    p.poll()


def assert_not_running(name):
    """Falha se existir processo cujo NOME é exatamente `name` (pgrep -x); linhas de comando que apenas
    mencionam o nome (shells, o próprio pgrep) não contam."""
    r = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True)
    pids = [int(x) for x in r.stdout.split() if alive(int(x))]
    if pids:
        raise RuntimeError(f"processo '{name}' já em execução: pids {pids}")

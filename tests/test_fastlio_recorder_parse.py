import importlib.util, sys, types
from types import SimpleNamespace as NS


def test_odom_to_line():
    for mod in ["rclpy", "rclpy.node", "rclpy.qos", "nav_msgs", "nav_msgs.msg"]:
        sys.modules.setdefault(mod, types.ModuleType(mod))
    sys.modules["rclpy.node"].Node = object
    sys.modules["nav_msgs.msg"].Odometry = object
    q = sys.modules["rclpy.qos"]; q.QoSProfile = q.ReliabilityPolicy = q.HistoryPolicy = object
    spec = importlib.util.spec_from_file_location("rec", "tools/fastlio_recorder.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    msg = NS(header=NS(stamp=NS(sec=5, nanosec=7)),
             pose=NS(pose=NS(position=NS(x=1, y=2, z=3), orientation=NS(x=0, y=0, z=0, w=1))))
    assert m.odom_to_line(msg).startswith("5.000000007 1.000000000 2.000000000 3.000000000")

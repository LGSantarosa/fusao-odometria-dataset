#!/usr/bin/env python3
"""Record /Odometry from FAST-LIO into TUM (ts from header = lidar_end_time) until idle timeout."""
import sys
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy


def odom_to_line(msg):
    s = msg.header.stamp
    p, q = msg.pose.pose.position, msg.pose.pose.orientation
    return f"{s.sec}.{s.nanosec:09d} {p.x:.9f} {p.y:.9f} {p.z:.9f} {q.x:.9f} {q.y:.9f} {q.z:.9f} {q.w:.9f}\n"


class Rec(Node):
    def __init__(self, path):
        super().__init__("fastlio_recorder")
        self.f = open(path, "w")
        self.last = time.time()
        qos = QoSProfile(depth=1000, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
        self.create_subscription(Odometry, "/Odometry", self.cb, qos)

    def cb(self, msg):
        self.f.write(odom_to_line(msg)); self.f.flush(); self.last = time.time()


def main():
    path, idle = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    rclpy.init(); n = Rec(path)
    try:
        while rclpy.ok() and time.time() - n.last < idle:
            rclpy.spin_once(n, timeout_sec=0.5)
    finally:
        n.f.close(); rclpy.shutdown()


if __name__ == "__main__":
    main()

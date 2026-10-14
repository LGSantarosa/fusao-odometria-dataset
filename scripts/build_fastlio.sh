#!/usr/bin/env bash
# Workspace ROS 2 próprio com symlinks para o FAST_LIO e o livox_ros_driver2 já usados no robô
# (Controle_robo_livox), sem alterar aquele projeto.
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p ros2_ws/src
SRC=/home/rbe-luis/Workspace/Controle_robo_livox/ros2_packages
ln -sfn "$SRC/FAST_LIO" ros2_ws/src/FAST_LIO
ln -sfn "$SRC/livox_ros_driver2" ros2_ws/src/livox_ros_driver2
source /opt/ros/jazzy/setup.bash
# livox_ros_driver2 exige a edição ROS2 explícita (ver Controle_robo_livox/setup_livox.sh);
# PCL estoura RAM com muitos jobs: sequencial e -j4.
cd ros2_ws && MAKEFLAGS=-j4 SHELL=/bin/bash colcon build --symlink-install --executor sequential \
  --packages-up-to fast_lio --cmake-args -DCMAKE_BUILD_TYPE=Release -DROS_EDITION=ROS2 -DHUMBLE_ROS=humble
git -C "$SRC/FAST_LIO" rev-parse HEAD > ../third_party_fastlio_commit.txt

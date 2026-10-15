#!/usr/bin/env bash
# Workspace ROS 2 próprio: FAST_LIO no commit fixado (third_party_fastlio_commit.txt) + patches versionados em
# third_party/FAST_LIO; livox_ros_driver2 (só tipos de mensagem) por symlink do projeto do robô
# (Controle_robo_livox), sem alterar aquele projeto.
# Uso: scripts/build_fastlio.sh [TP_DIR]   (padrão: third_party)
set -eo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
TP=$(realpath -m "${1:-third_party}")
source scripts/lib_pin.sh
PIN=$(cat third_party_fastlio_commit.txt)   # atualizar o pin = editar esse arquivo
mkdir -p "$TP" ros2_ws/src
[ -d "$TP/FAST_LIO" ] || { git clone -q https://github.com/Ericsii/FAST_LIO.git "$TP/FAST_LIO" \
  && git -C "$TP/FAST_LIO" checkout -q "$PIN" && git -C "$TP/FAST_LIO" submodule update -q --init --recursive; }
apply_patches "$TP/FAST_LIO" "$ROOT"/patches/fastlio/*.patch
verify_pin "$TP/FAST_LIO" "$PIN" "$ROOT"/patches/fastlio/*.patch
ln -sfn "$TP/FAST_LIO" ros2_ws/src/FAST_LIO
ln -sfn /home/rbe-luis/Workspace/Controle_robo_livox/ros2_packages/livox_ros_driver2 ros2_ws/src/livox_ros_driver2
source /opt/ros/jazzy/setup.bash
# livox_ros_driver2 exige a edição ROS2 explícita (ver Controle_robo_livox/setup_livox.sh);
# PCL estoura RAM com muitos jobs: sequencial e -j4.
cd ros2_ws && MAKEFLAGS=-j4 SHELL=/bin/bash colcon build --symlink-install --executor sequential \
  --packages-up-to fast_lio --cmake-args -DCMAKE_BUILD_TYPE=Release -DROS_EDITION=ROS2 -DHUMBLE_ROS=humble

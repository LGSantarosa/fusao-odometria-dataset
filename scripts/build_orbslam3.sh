#!/usr/bin/env bash
# Build reprodutível do ORB-SLAM3 (commit fixo + patches versionados) e do runner estéreo com log causal.
# Uso: scripts/build_orbslam3.sh [TP_DIR]   (padrão: third_party)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
TP=$(realpath -m "${1:-third_party}")
mkdir -p "$TP" && cd "$TP"
J=${J:-6}
source "$ROOT/scripts/lib_pin.sh"

pin_clone Pangolin https://github.com/stevenlovegrove/Pangolin.git 7364b59a58045d1c429b146e44f6f088fd1cc518
verify_pin Pangolin 7364b59a58045d1c429b146e44f6f088fd1cc518
cmake -S Pangolin -B Pangolin/build -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF \
  -DBUILD_TOOLS=OFF -DBUILD_PANGOLIN_PYTHON=OFF -DCMAKE_INSTALL_PREFIX="$TP/local" >/dev/null
cmake --build Pangolin/build -j"$J" --target install >/dev/null

pin_clone ORB_SLAM3 https://github.com/UZ-SLAMLab/ORB_SLAM3.git 4452a3c4ab75
apply_patches ORB_SLAM3 "$ROOT"/patches/orbslam3/*.patch
verify_pin ORB_SLAM3 4452a3c4ab75 "$ROOT"/patches/orbslam3/*.patch
cd ORB_SLAM3
for d in DBoW2 g2o Sophus; do
  (cd Thirdparty/$d && cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF >/dev/null && cmake --build build -j"$J" >/dev/null)
done
[ -f Vocabulary/ORBvoc.txt ] || (cd Vocabulary && tar xf ORBvoc.txt.tar.gz)
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$TP/local" >/dev/null
cmake --build build -j"$J" --target ORB_SLAM3 >/dev/null

cd "$ROOT"
B="$TP/vo_runners_build"
cmake -S tools/vo_runners -B "$B" -DCMAKE_BUILD_TYPE=Release -DORB_SLAM3_DIR="$TP/ORB_SLAM3" \
  -DCMAKE_PREFIX_PATH="$TP/local" >/dev/null
cmake --build "$B" -j"$J" --target orbslam3_stereo_log >/dev/null
mkdir -p "$TP/bin" && cp "$B/orbslam3_stereo_log" "$TP/bin/"
echo "ok: $TP/bin/orbslam3_stereo_log ($(ldd "$TP/bin/orbslam3_stereo_log" | grep -c 'not found') libs não encontradas)"

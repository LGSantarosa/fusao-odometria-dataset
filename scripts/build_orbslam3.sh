#!/usr/bin/env bash
# Build reprodutível do ORB-SLAM3 (commit fixo + patches versionados) e do runner estéreo com log causal.
# Uso: scripts/build_orbslam3.sh [TP_DIR]   (padrão: third_party)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
TP=$(realpath -m "${1:-third_party}")
mkdir -p "$TP" && cd "$TP"
J=${J:-6}

[ -d Pangolin ] || { git clone -q https://github.com/stevenlovegrove/Pangolin.git && git -C Pangolin checkout -q 7364b59a58045d1c429b146e44f6f088fd1cc518; }
cmake -S Pangolin -B Pangolin/build -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF \
  -DBUILD_TOOLS=OFF -DBUILD_PANGOLIN_PYTHON=OFF -DCMAKE_INSTALL_PREFIX="$TP/local" >/dev/null
cmake --build Pangolin/build -j"$J" --target install >/dev/null

[ -d ORB_SLAM3 ] || { git clone -q https://github.com/UZ-SLAMLab/ORB_SLAM3.git && git -C ORB_SLAM3 checkout -q 4452a3c4ab75; }
cd ORB_SLAM3
for p in "$ROOT"/patches/orbslam3/*.patch; do   # idempotente: aplica se ainda não aplicado
  if git apply --check "$p" 2>/dev/null; then git apply "$p"; else git apply --check -R "$p"; fi
done
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

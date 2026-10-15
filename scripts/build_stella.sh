#!/usr/bin/env bash
# Build reprodutível do stella_vslam (commits fixos + patches versionados) e do runner estéreo com log causal.
# Uso: scripts/build_stella.sh [TP_DIR]   (padrão: third_party)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
TP=$(realpath -m "${1:-third_party}")
P="$TP/local"
J=${J:-6}
source "$ROOT/scripts/lib_pin.sh"
mkdir -p "$TP" && cd "$TP"

pin_clone g2o https://github.com/RainerKuemmerle/g2o.git e8df2004e07ea8f5b8e6a8b9f2dc067b45b45036
verify_pin g2o e8df2004e07ea8f5b8e6a8b9f2dc067b45b45036
cmake -S g2o -B g2o/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$P" -DBUILD_SHARED_LIBS=ON \
  -DG2O_BUILD_APPS=OFF -DG2O_BUILD_EXAMPLES=OFF -DG2O_USE_OPENGL=OFF -DBUILD_UNITTESTS=OFF >/dev/null
cmake --build g2o/build -j"$J" --target install >/dev/null

pin_clone FBoW https://github.com/stella-cv/FBoW.git c6e3c29e3332
verify_pin FBoW c6e3c29e3332
cmake -S FBoW -B FBoW/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$P" >/dev/null
cmake --build FBoW/build -j"$J" --target install >/dev/null

[ -d stella_vslam ] || { git clone -q https://github.com/stella-cv/stella_vslam.git && git -C stella_vslam checkout -q e445b5452535 \
  && git -C stella_vslam submodule update -q --init --recursive; }
apply_patches stella_vslam "$ROOT"/patches/stella/*.patch
verify_pin stella_vslam e445b5452535 "$ROOT"/patches/stella/*.patch
cmake -S stella_vslam -B stella_vslam/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$P" \
  -DCMAKE_PREFIX_PATH="$P" -DCMAKE_INSTALL_RPATH="$P/lib" >/dev/null
cmake --build stella_vslam/build -j"$J" --target install >/dev/null
[ -f orb_vocab.fbow ] || curl -sfL https://github.com/stella-cv/FBoW_orb_vocab/raw/708407ae4cd5/orb_vocab.fbow -o orb_vocab.fbow

cd "$ROOT"
B="$TP/vo_runners_build_stella"
cmake -S tools/vo_runners -B "$B" -DCMAKE_BUILD_TYPE=Release -DSTELLA_PREFIX="$P/lib/cmake/stella_vslam" \
  -DCMAKE_PREFIX_PATH="$P" >/dev/null
cmake --build "$B" -j"$J" --target stella_stereo_log >/dev/null
mkdir -p "$TP/bin" && cp "$B/stella_stereo_log" "$TP/bin/"
echo "ok: $TP/bin/stella_stereo_log ($(ldd "$TP/bin/stella_stereo_log" | grep -c 'not found') libs não encontradas)"

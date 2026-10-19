#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH   # o ROS (via .bashrc) poluiria o venv e o pip freeze
python3 -m venv .venv
.venv/bin/pip install -U pip
TORCH_INDEX=https://download.pytorch.org/whl/cpu   # torch só em CPU (modelo de fusão)
if [ -f requirements.lock ]; then
  .venv/bin/pip install -r requirements.lock --extra-index-url "$TORCH_INDEX"
  .venv/bin/pip install --no-deps -e .
else
  .venv/bin/pip install -e '.[dev]' --extra-index-url "$TORCH_INDEX"
  .venv/bin/pip freeze --exclude-editable > requirements.lock   # trava versões na 1ª instalação
fi
.venv/bin/python -c "import sys, open3d, kiss_icp, rosbags, pandas, torch; assert sys.version_info[:2] == (3, 12); print('env ok')"

#!/usr/bin/env bash
cd "$(dirname "$0")/.."
exec env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest "$@"

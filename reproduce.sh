#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
glyph_entrypoint=reproduce_tables.py
glyph_requirements=requirements.txt
if [[ "${1:-}" == "--refit" ]]; then
  shift
  glyph_entrypoint=reproduce_from_activations.py
  glyph_requirements=requirements-refit.txt
fi
if [[ -n "${GLYPH_PYTHON:-}" ]]; then
  "$GLYPH_PYTHON" "$glyph_entrypoint" "$@"
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -r "$glyph_requirements"
  .venv/bin/python "$glyph_entrypoint" "$@"
fi

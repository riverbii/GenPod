#!/bin/bash
set -e

echo "🧪 Running GenPod Unit Tests..."
cd "$(dirname "$0")"

echo "🧹 Running Ruff Lint..."
uv run ruff check .

# Use uv run with PYTHONPATH set to src
uv run env PYTHONPATH=src pytest

if [ $? -eq 0 ]; then
    echo "✅ Tests Passed!"
    exit 0
else
    echo "❌ Tests Failed!"
    exit 1
fi

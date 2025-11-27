#!/bin/bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc
set -euo pipefail

start=$(date +%s)

echo "==============================="
echo "🔷 Starting full CFD pipeline..."
echo "==============================="

echo "➡️  Running mesh pipeline..."
chmod +x Allmesh.sh
./Allmesh.sh

echo "➡️  Running solver..."
chmod +x Solve.sh
./Solve.sh

echo "==============================="
echo "🎉 Pipeline complete!"
echo "==============================="

end=$(date +%s)
echo "⏱ Total pipeline runtime: $((end-start)) seconds"
echo "$((end-start))" > pipeline_runtime.txt


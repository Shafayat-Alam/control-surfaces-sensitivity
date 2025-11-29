#!/bin/bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc
set -euo pipefail

start=$(date +%s)

echo "📊 Launching ParaView viewer..."

rm -f para.foam
touch para.foam

paraview para.foam

end=$(date +%s)
echo "⏱ Runtime: $((end-start)) seconds"

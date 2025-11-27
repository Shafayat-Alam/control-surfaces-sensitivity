#!/bin/bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc
set -euo pipefail

start=$(date +%s)

echo "🧹 Cleaning OpenFOAM case..."

echo " - Removing processor* directories..."
rm -rf processor*

echo " - Removing mesh (constant/polyMesh)..."
rm -rf constant/polyMesh

echo " - Removing surfaceFeatureExtract outputs..."
rm -rf constant/extendedFeatureEdgeMesh
rm -rf constant/triSurface/*.eMesh

echo " - Removing logs folders..."
rm -rf logs_mesh logs_sim logs

echo " - Removing postProcessing (if exists)..."
rm -rf postProcessing

echo " - Removing time directories except 0..."
for d in *; do
    if [[ -d "$d" ]]; then
        case "$d" in
            0 | constant | system)
                ;;
            ''|*[!0-9.]*)
                ;;
            *)
                echo "   removing $d"
                rm -rf "$d"
                ;;
        esac
    fi
done

echo " - Removing dynamicCode (if exists)..."
rm -rf dynamicCode

echo "✨ Clean complete!"

end=$(date +%s)
echo "⏱ Runtime: $((end-start)) seconds"

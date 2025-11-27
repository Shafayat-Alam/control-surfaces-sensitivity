#!/bin/bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc
set -e

start=$(date +%s)

LOGDIR="logs_mesh"
NPROCS=6

rm -rf "$LOGDIR" processor* constant/polyMesh
mkdir -p "$LOGDIR"

echo "🧱 Running blockMesh..."
blockMesh > "$LOGDIR/blockMesh.log" 2>&1

echo "🧭 Running surfaceFeatureExtract..."
surfaceFeatureExtract > "$LOGDIR/surfaceFeatureExtract.log" 2>&1

echo "🧩 Decomposing for snappyHexMesh..."
decomposePar > "$LOGDIR/decomposePar_mesh.log" 2>&1

echo "📂 Copying STL to each processor domain..."
for d in processor*/constant; do
    mkdir -p "$d/triSurface"
    cp -r constant/triSurface/* "$d/triSurface/"
done

echo "⚙️ Running snappyHexMesh in parallel..."
export OMPI_MCA_btl=^openib
mpirun -np "$NPROCS" snappyHexMesh -parallel -overwrite \
    > "$LOGDIR/snappyHexMesh.log" 2>&1

echo "🔗 Reconstructing mesh..."
reconstructParMesh -constant > "$LOGDIR/reconstructMesh.log" 2>&1

rm -rf processor*

echo "🔍 Running checkMesh..."
checkMesh > "$LOGDIR/checkMesh.log" 2>&1

echo "✨ Meshing complete!"

end=$(date +%s)
echo "⏱ Runtime: $((end-start)) seconds"
echo "$((end-start))" > "$LOGDIR/runtime_seconds.txt"


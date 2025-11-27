#!/bin/bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc
set -euo pipefail

start=$(date +%s)

LOGDIR="logs_sim"
NPROCS=6

rm -rf "$LOGDIR" processor*
mkdir -p "$LOGDIR"

echo "🧩 Decomposing domain..."
decomposePar > "$LOGDIR/decomposePar_solve.log" 2>&1

echo "🚀 Running rhoPimpleFoam..."
export OMPI_MCA_btl=^openib
mpirun -np "$NPROCS" rhoPimpleFoam -parallel \
    > "$LOGDIR/rhoPimpleFoam.log" 2>&1

echo "🔗 Reconstructing..."
reconstructPar > "$LOGDIR/reconstructPar.log" 2>&1

echo "✨ Simulation complete!"

end=$(date +%s)
echo "⏱ Runtime: $((end-start)) seconds"
echo "$((end-start))" > "$LOGDIR/runtime_seconds.txt"


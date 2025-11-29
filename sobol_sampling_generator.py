#!/usr/bin/env python3
"""
Generate Sobol-sampled OpenFOAM cases for a trapezoidal fin:

- Baseline case folder: ./case_baseline
- Output cases folder:  ./sobol_cases
- 4 geometry parameters varied with Sobol sampling:
    cr, ct, s, xr  ∈  [0.75, 1.25] * BASE values
- Mach number ∈ [0.3, 0.7]; inlet velocity set in 0/U
- For each case:
    * copy case_baseline → sobol_cases/case_XXX
    * create a new STL for the fin
    * remove baseline STL(s) from triSurface
    * update snappyHexMeshDict & surfaceFeatureExtractDict to use new STL/eMesh
    * scale blockMeshDict vertices in x,y to match new geometry
    * update inlet velocity in 0/U using Mach * a_ref
"""

import os
import shutil
import numpy as np
from pathlib import Path
import multiprocessing as mp
import re

import trimesh
from scipy.stats import qmc  # Sobol sampler


# =====================================================
# GLOBAL CONFIG
# =====================================================

BASE_DIR      = os.getcwd()
BASELINE_DIR  = os.path.join(BASE_DIR, "case_baseline")
OUT_DIR       = os.path.join(BASE_DIR, "sobol_cases")

N_SAMPLES     = 150          # number of cases
N_PROCS       = max(1, mp.cpu_count() // 2)  # conservative for WSL

# Baseline geometry (MUST match case_baseline geometry)
BASE = {
    "cr": 5.88,   # root chord
    "ct": 2.27,   # tip chord
    "s":  5.86,   # span
    "xr": 1.46,   # sweep
    "t":  0.10    # thickness (kept fixed)
}

# Multiplicative range for geometry: 0.75x → 1.25x
LOW_FACTOR  = 0.75
HIGH_FACTOR = 1.25

# Mach range
MACH_MIN = 0.3
MACH_MAX = 0.7

# Speed of sound for inlet velocity
A_REF = 340.0  # m/s


# =====================================================
# GEOMETRY: build STL
# =====================================================

def build_stl(cr, ct, s, xr, t, filename):
    """
    Build a trapezoidal fin STL, matching the baseline orientation.
    2D base (x-y), extruded in z, then rotated into OpenFOAM frame.
    """
    # 2D trapezoid in (x, y)
    v2d = np.array([
        [0.0,     0.0],
        [cr,      0.0],
        [xr + ct, s  ],
        [xr,      s  ]
    ])

    # Extrude in thickness direction (z)
    verts = []
    for dz in [0.0, t]:
        for v in v2d:
            verts.append([v[0], v[1], dz])
    verts = np.array(verts)

    # Rotate into OpenFOAM frame (same as baseline)
    R = np.array([[1, 0, 0],
                  [0, 0, 1],
                  [0, 1, 0]])
    verts = verts @ R.T

    # Faces for a hex-like wedge
    faces = [
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0]
    ]

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh.export(filename)


# =====================================================
# FILE EDIT HELPERS
# =====================================================

def update_snappy_dict(snappy_path, stl_name):
    """
    Update STL and eMesh names in snappyHexMeshDict.
    Replaces any *.stl and *.eMesh with the new names.
    """
    stem = Path(stl_name).stem
    with open(snappy_path, "r") as f:
        text = f.read()

    # Replace any .stl reference with our STL name
    text = re.sub(r"\S+\.stl", stl_name, text)

    # Replace any .eMesh reference with stem.eMesh
    text = re.sub(r"\S+\.eMesh", f"{stem}.eMesh", text)

    with open(snappy_path, "w") as f:
        f.write(text)


def update_surface_feature_dict(sfe_path, stl_name):
    """
    Update STL name in surfaceFeatureExtractDict.
    """
    with open(sfe_path, "r") as f:
        text = f.read()

    text = re.sub(r"\S+\.stl", stl_name, text)

    with open(sfe_path, "w") as f:
        f.write(text)


def scale_blockMesh_vertices(bmd_path, sx, sy):
    """
    Scale x and y of all vertices in blockMeshDict by sx, sy.
    z is left unchanged.
    """
    with open(bmd_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    in_vertices = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("vertices"):
            in_vertices = True
            new_lines.append(line)
            continue

        if in_vertices and stripped.startswith(");"):
            in_vertices = False
            new_lines.append(line)
            continue

        if in_vertices and stripped.startswith("(") and stripped.endswith(")"):
            content = stripped[1:-1].split()
            if len(content) == 3:
                try:
                    x = float(content[0])
                    y = float(content[1])
                    z = float(content[2])

                    x *= sx
                    y *= sy

                    prefix = line.split("(")[0]
                    new_lines.append(f"{prefix}({x:.6f} {y:.6f} {z})\n")
                    continue
                except ValueError:
                    pass  # fall through and keep original

        new_lines.append(line)

    with open(bmd_path, "w") as f:
        f.writelines(new_lines)


def set_inlet_velocity_U(U_file, mach):
    """
    Set inlet velocity to Mach * A_REF in 0/U.
    Only modifies the inlet{... value uniform (...) } block.
    """
    velocity = mach * A_REF

    with open(U_file, "r") as f:
        text = f.read()

    # Replace vector inside inlet block's value uniform (...)
    # DOTALL so it crosses line breaks.
    pattern = r"(inlet\s*\{[^}]*?value\s+uniform\s*)\([^)]+\)"
    replacement = rf"\1({velocity:.6f} 0 0)"

    new_text, n_subs = re.subn(pattern, replacement, text, flags=re.DOTALL)
    if n_subs == 0:
        print(f"[WARN] Did not find inlet value in {U_file}; file unchanged.")
    else:
        text = new_text

    with open(U_file, "w") as f:
        f.write(text)


# =====================================================
# CASE GENERATION
# =====================================================

def make_case(args):
    """
    Build a single case_i:
    - copy baseline case
    - generate STL
    - update snappy, surfaceFeature, blockMesh, U
    - remove baseline STL(s)
    """
    idx, (cr, ct, s, xr, mach) = args

    case_name = f"case_{idx:03d}"
    case_dir = os.path.join(OUT_DIR, case_name)

    # Clean any previous version
    if os.path.exists(case_dir):
        shutil.rmtree(case_dir)

    # 1) Copy baseline case
    shutil.copytree(BASELINE_DIR, case_dir)

    # 2) Create STL for this case
    tri_dir = os.path.join(case_dir, "constant", "triSurface")
    os.makedirs(tri_dir, exist_ok=True)

    stl_name = f"geom_{idx:03d}.stl"
    stl_path = os.path.join(tri_dir, stl_name)

    build_stl(cr, ct, s, xr, BASE["t"], stl_path)

    # 3) Remove any other STL (e.g. baseline.stl)
    for fname in os.listdir(tri_dir):
        if fname.endswith(".stl") and fname != stl_name:
            try:
                os.remove(os.path.join(tri_dir, fname))
            except OSError:
                pass

    # 4) Update dictionaries
    snappy_path = os.path.join(case_dir, "system", "snappyHexMeshDict")
    sfe_path    = os.path.join(case_dir, "system", "surfaceFeatureExtractDict")
    bmd_path    = os.path.join(case_dir, "system", "blockMeshDict")
    U_file      = os.path.join(case_dir, "0", "U")

    update_snappy_dict(snappy_path, stl_name)
    update_surface_feature_dict(sfe_path, stl_name)

    # 5) Scale blockMesh vertices
    base_x_len = BASE["cr"] + BASE["xr"] + BASE["ct"]
    new_x_len  = cr + xr + ct
    sx = new_x_len / base_x_len
    sy = s / BASE["s"]

    scale_blockMesh_vertices(bmd_path, sx, sy)

    # 6) Set inlet Mach number via 0/U
    set_inlet_velocity_U(U_file, mach)

    print(
        f"[CASE] {case_name}: Mach={mach:.3f}, "
        f"cr={cr:.3f}, ct={ct:.3f}, s={s:.3f}, xr={xr:.3f}, "
        f"sx={sx:.3f}, sy={sy:.3f}"
    )


# =====================================================
# MAIN
# =====================================================

def main():
    if not os.path.isdir(BASELINE_DIR):
        raise RuntimeError("ERROR: 'case_baseline' folder not found next to this script.")

    # Sobol sampler: 5 dimensions -> (cr, ct, s, xr, Mach)
    sampler = qmc.Sobol(d=5, scramble=True)
    U = sampler.random(N_SAMPLES)  # N_SAMPLES x 5 in [0,1)

    # Map Sobol samples to geometry ranges
    CR = BASE["cr"] * (LOW_FACTOR + U[:, 0] * (HIGH_FACTOR - LOW_FACTOR))
    CT = BASE["ct"] * (LOW_FACTOR + U[:, 1] * (HIGH_FACTOR - LOW_FACTOR))
    S  = BASE["s"]  * (LOW_FACTOR + U[:, 2] * (HIGH_FACTOR - LOW_FACTOR))
    XR = BASE["xr"] * (LOW_FACTOR + U[:, 3] * (HIGH_FACTOR - LOW_FACTOR))

    # Mach number range
    MACH = MACH_MIN + U[:, 4] * (MACH_MAX - MACH_MIN)

    samples = np.vstack([CR, CT, S, XR, MACH]).T  # shape (N_SAMPLES, 5)

    # Prepare output folder
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"[INFO] Creating {N_SAMPLES} Sobol cases in '{OUT_DIR}' ...")

    args = [(i + 1, samples[i]) for i in range(N_SAMPLES)]

    # Parallel generation (conservative number of processes for WSL)
    with mp.Pool(N_PROCS) as pool:
        pool.map(make_case, args)

    print("\n=== DONE: All Sobol CFD cases generated in 'sobol_cases/' ===")


if __name__ == "__main__":
    main()

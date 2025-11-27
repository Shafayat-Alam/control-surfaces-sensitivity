#!/usr/bin/env python3
import os
import shutil
import numpy as np
import trimesh
import multiprocessing as mp

# ======================
# CONFIG
# ======================

BASE_DIR   = os.getcwd()
TEMPLATE   = os.path.join(BASE_DIR, "case_template")
BASELINE_STL = "baseline.stl"

CASE_FOLDERS = ["cr_cases", "ct_cases", "s_cases", "xr_cases"]
PARAMS       = ["cr", "ct", "s", "xr"]

BASE = {
    "cr": 5.88,
    "ct": 2.27,
    "s":  5.86,
    "xr": 1.46,
    "t":  0.10
}

NUM_STEPS    = 5       # 5 up, 5 down
STEP_PERCENT = 0.04    # 4% per step

N_PROCS = max(1, mp.cpu_count() - 1)


# ======================
# GEOMETRY (FIN BUILDER)
# ======================

def build_stl(cr, ct, s, xr, t, filename):
    """Build a simple extruded trapezoidal fin STL."""
    v2d = np.array([
        [0,       0],
        [cr,      0],
        [xr + ct, s],
        [xr,      s]
    ])

    # Extrude into thickness t
    verts = []
    for dz in [0, t]:
        for v in v2d:
            verts.append([v[0], v[1], dz])

    verts = np.array(verts)

    # Rotate (y,z)->(z,y)
    R = np.array([
        [1,0,0],
        [0,0,1],
        [0,1,0]
    ])
    verts = verts @ R.T

    # Connectivity
    faces = [
        [0,1,2], [0,2,3],
        [4,6,5], [4,7,6],
        [0,4,5], [0,5,1],
        [1,5,6], [1,6,2],
        [2,6,7], [2,7,3],
        [3,7,4], [3,4,0]
    ]

    trimesh.Trimesh(vertices=verts, faces=faces).export(filename)


# ======================
# DICTIONARY WRITERS
# ======================

def blockMesh_text():
    return """/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |
| \\      /  F ield         |  OpenFOAM: The Open Source CFD Toolbox
|  \\    /   O peration     |  Version:  v2412
|   \\  /    A nd           |
|    \\/     M anipulation  |
\*---------------------------------------------------------------------------*/

FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}

convertToMeters 1;

// Rotated bounding-box by +10 degrees about z-axis

vertices
(
    // z = 0 plane
    (-48.663  -69.185   0)   // 0
    ( 69.185  -48.663   0)   // 1
    ( 48.663   69.185   0)   // 2
    (-69.185   48.663   0)   // 3

    // z = 60 plane
    (-48.663  -69.185  60)   // 4
    ( 69.185  -48.663  60)   // 5
    ( 48.663   69.185  60)   // 6
    (-69.185   48.663  60)   // 7
);

blocks
(
    hex (0 1 2 3 4 5 6 7) (280 150 150) simpleGrading (5 1 3)
);

boundary
(
    inlet
    {
        type patch;
        faces ((0 3 7 4));
    }

    outlet
    {
        type patch;
        faces ((1 2 6 5));
    }

    walls
    {
        type wall;
        faces
        (
            (0 1 5 4)
            (2 3 7 6)
            (0 1 2 3)
            (4 5 6 7)
        );
    }
);

mergePatchPairs();
"""


def make_surfaceFeatureExtractDict(stl_name):
    return f"""/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |
| \\      /  F ield         |  OpenFOAM: The Open Source CFD Toolbox
|  \\    /   O peration     |  Version:  v2412
|   \\  /    A nd           |
|    \\/     M anipulation  |
\*---------------------------------------------------------------------------*/

FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      surfaceFeatureExtractDict;
}}

baseline.stl
{{
    extractionMethod        extractFromSurface;

    extractFromSurfaceCoeffs
    {{
        includedAngle       25;     // MUCH FINER (default was 150)
        geometricTest       yes;
    }}

    writeObj                yes;
}}

// ************************************************************************* //
"""


def make_snappyHexMeshDict(stl_name):
    return f"""/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
\*---------------------------------------------------------------------------*/

FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}}

castellatedMesh true;
snap            true;
addLayers       false;   // can be turned on later if you want BL layers

// ==========================================================================
// GEOMETRY
// ==========================================================================
geometry
{{
    baseline.stl
    {{
        type triSurfaceMesh;
        name senPam;
    }}
}}

// ==========================================================================
// CASTELLATED MESH CONTROLS  (HIGH RESOLUTION)
// ==========================================================================
castellatedMeshControls
{{
    // allow a lot of cells
    maxLocalCells         2e6;
    maxGlobalCells        2e7;
    minRefinementCells    20;
    nCellsBetweenLevels   2;

    // sharp feature capture
    features
    (
        {{
            file "baseline.eMesh";
            level 4;          // fine edge refinement
        }}
    );

    allowFreeStandingZoneFaces true;

    // strong surface refinement on fin
    refinementSurfaces
    {{
        senPam
        {{
            // (far-field level, near-surface level)
            level (3 5);      // coarse in far field, very fine at fin
            patchInfo
            {{
                type wall;
            }}
        }}
    }}

    // wake refinement box downstream of the fin
    refinementRegions
    {{
        wakeBox
        {{
            mode inside;
            levels ((4 4));   // fine wake
            box
            {{
                type searchableBox;
                // adjust if needed, but this matches your rotated domain scale
                min (0   -20 -20);
                max (80   20  20);
            }}
        }}
    }}

    resolveFeatureAngle    25;
    locationInMesh         (0 0 10);
}}

// ==========================================================================
// SNAP CONTROLS  (AGGRESSIVE BUT STABLE)
// ==========================================================================
snapControls
{{
    nSmoothPatch           15;
    nSmoothInternal        5;
    nSmoothSurfaceNormals  5;

    tolerance              1.0;
    nSolveIter             120;
    nRelaxIter             10;

    explicitFeatureSnap    true;
    implicitFeatureSnap    true;
    multiRegionFeatureSnap true;

    snapTol                0.95;
    detectNearSurfaces     snap;
}}

// ==========================================================================
// ADD LAYERS (OFF, BUT CONFIG READY)
// ==========================================================================
addLayersControls
{{
    relativeSizes          true;
    expansionRatio         1.1;
    finalLayerThickness    0.2;
    minThickness           0.05;
    nGrow                  0;
    layers                 {{}};
}}

// ==========================================================================
// MESH QUALITY (STRICTER)
// ==========================================================================
meshQualityControls
{{
    maxNonOrtho            65;
    maxBoundarySkewness    4;
    maxInternalSkewness    4;
    maxConcave             80;

    minVol                 1e-14;
    minTetQuality          1e-10;
    minArea                1e-13;
    minTwist               0.02;
    minDeterminant         0.0005;
    minFaceWeight          0.02;
    minVolRatio            0.01;
    minTriangleTwist       0.02;

    nSmoothScale           6;
    errorReduction         0.7;
    relaxed                true;
    nRelaxIter             8;
}}

mergeTolerance 1e-8;

// ************************************************************************* //
"""


def write_case_files(case_dir, stl_filename):
    system_dir = os.path.join(case_dir, "system")
    os.makedirs(system_dir, exist_ok=True)

    with open(os.path.join(system_dir, "blockMeshDict"), "w") as f:
        f.write(blockMesh_text())

    with open(os.path.join(system_dir, "surfaceFeatureExtractDict"), "w") as f:
        f.write(make_surfaceFeatureExtractDict(stl_filename))

    with open(os.path.join(system_dir, "snappyHexMeshDict"), "w") as f:
        f.write(make_snappyHexMeshDict(stl_filename))


# ======================
# STL GENERATION
# ======================

def generate_perturbation_stls():
    for param in PARAMS:
        folder = os.path.join(BASE_DIR, f"{param}_cases")
        os.makedirs(folder, exist_ok=True)

        for sign in (+1, -1):
            sign_tag = "+" if sign > 0 else "-"
            for step in range(1, NUM_STEPS + 1):
                scale = 1 + sign * STEP_PERCENT * step

                cr = BASE["cr"]
                ct = BASE["ct"]
                s  = BASE["s"]
                xr = BASE["xr"]
                t  = BASE["t"]

                if param == "cr":
                    cr = BASE["cr"] * scale
                elif param == "ct":
                    ct = BASE["ct"] * scale
                elif param == "s":
                    s  = BASE["s"] * scale
                elif param == "xr":
                    xr = BASE["xr"] * scale

                stl_name = f"{param}_{sign_tag}4percent_step{step}.stl"
                stl_path = os.path.join(folder, stl_name)

                build_stl(cr, ct, s, xr, t, stl_path)
                print(f"[STL] {stl_path} (scale {scale:.3f})")


# ======================
# CREATE ONE BASELINE CASE
# ======================

def create_single_baseline_case():
    baseline_dir = os.path.join(BASE_DIR, "case_baseline")

    if not os.path.exists(baseline_dir):
        shutil.copytree(TEMPLATE, baseline_dir)

    os.makedirs(os.path.join(baseline_dir, "constant", "triSurface"), exist_ok=True)

    write_case_files(baseline_dir, BASELINE_STL)

    print(f"[BASELINE] {baseline_dir}")


# ======================
# PERTURBATION CASE BUILDER
# ======================

def make_one_case(folder_name, stl_file):
    case_root = os.path.join(BASE_DIR, folder_name)
    stl_path  = os.path.join(case_root, stl_file)

    case_name = f"case_{os.path.splitext(stl_file)[0]}"
    new_case = os.path.join(case_root, case_name)

    if not os.path.exists(new_case):
        shutil.copytree(TEMPLATE, new_case)

    tri_dir = os.path.join(new_case, "constant", "triSurface")
    os.makedirs(tri_dir, exist_ok=True)

    # remove baseline.stl if present
    old = os.path.join(tri_dir, BASELINE_STL)
    if os.path.exists(old):
        os.remove(old)

    shutil.move(stl_path, os.path.join(tri_dir, stl_file))

    write_case_files(new_case, stl_file)

    print(f"[CASE] {new_case}")


def collect_jobs():
    jobs = []
    for folder in CASE_FOLDERS:
        path = os.path.join(BASE_DIR, folder)
        for f in os.listdir(path):
            if f.endswith(".stl"):
                jobs.append((folder, f))
    return jobs


def build_cases_parallel():
    jobs = collect_jobs()
    print(f"[INFO] Found {len(jobs)} perturbation STLs.\n")
    if jobs:
        with mp.Pool(N_PROCS) as pool:
            pool.starmap(make_one_case, jobs)


# ======================
# MAIN
# ======================

def main():
    print("=== STEP 1: Generating perturbation STLs ===")
    generate_perturbation_stls()

    print("\n=== STEP 2: Creating SINGLE baseline case ===")
    create_single_baseline_case()

    print("\n=== STEP 3: Building perturbation cases ===")
    build_cases_parallel()

    print("\n=== ALL DONE ===")


if __name__ == "__main__":
    mp.freeze_support()
    main()

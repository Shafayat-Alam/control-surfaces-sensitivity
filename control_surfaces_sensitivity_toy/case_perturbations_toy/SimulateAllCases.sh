#!/bin/bash

# master script to run Simulate.sh in every generated case folder

PARAM_FOLDERS=("cr_cases" "ct_cases" "s_cases" "xr_cases")

echo "=== Running ALL perturbation cases ==="

for param in "${PARAM_FOLDERS[@]}"; do
    echo ""
    echo "➡ Entering parameter folder: $param"

    # loop inside cr_cases/, ct_cases/, etc.
    for case_dir in "$param"/*/; do
        
        # skip if not a directory
        [ -d "$case_dir" ] || continue

        # check if Simulate.sh exists
        if [ -f "$case_dir/Simulate.sh" ]; then
            echo "---- Running: $case_dir/Simulate.sh ----"
            (
                cd "$case_dir" || exit
                chmod +x Simulate.sh
                ./Simulate.sh
            )
        else
            echo "Skipping $case_dir (no Simulate.sh found)"
        fi
    done
done

echo ""
echo "=== ALL SIMULATIONS COMPLETE ==="

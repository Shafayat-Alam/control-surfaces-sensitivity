#!/bin/bash

echo "==========================================="
echo "      MASTER RUN: Executing All Cases"
echo "==========================================="

# -----------------------------------------------------
# 1) RUN BASELINE CASE
# -----------------------------------------------------

if [ -d "case_baseline" ]; then
    echo "➡ Running BASELINE case (case_baseline)"

    if [ -f "case_baseline/Simulate.sh" ]; then
        (
            cd case_baseline || exit
            chmod +x Simulate.sh
            ./Simulate.sh
        )
    else
        echo "⚠ WARNING: case_baseline/Simulate.sh not found."
    fi
else
    echo "⚠ WARNING: case_baseline folder not found."
fi


# -----------------------------------------------------
# 2) RUN ALL SOBOL CASES
# -----------------------------------------------------

if [ -d "sobol_cases" ]; then
    echo ""
    echo "➡ Running ALL Sobol-generated cases in sobol_cases/"

    for case_dir in sobol_cases/*/; do
        
        # skip if not directory
        [ -d "$case_dir" ] || continue

        # check Simulate.sh inside case
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
else
    echo "⚠ WARNING: sobol_cases folder not found."
fi


echo ""
echo "==========================================="
echo "      ALL SIMULATIONS COMPLETED"
echo "==========================================="

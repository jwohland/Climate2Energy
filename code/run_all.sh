#!/bin/bash
mkdir -p ../logs
for bc_realization in A B C
do
    python compute_bias_correction_prep.py ${bc_realization}  # Input files for bias correction
    for scenario in historical SSP370
    do
      for realization in A B C
      do
        conda activate CESM2energy
        # todo 1) bias_correct.py; 2) compute_wind_generation.py; 3) compute PV_generation.py
        python compute_generation.py ${scenario} ${realization} ${bc_realization} > ../logs/compute_generation_log_$(date +%Y_%m_%d_%H).txt
        conda deactivate
        conda activate demand_ninja
        python compute_demand.py ${scenario} ${realization} ${bc_realization} > ../logs/compute_demand_log_$(date +%Y_%m_%d_%H).txt
        conda deactivate
      done
    done
done
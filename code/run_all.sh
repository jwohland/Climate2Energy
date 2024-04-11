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
        python compute_bias_correction.py ${scenario} ${realization} ${bc_realization}
        python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind > ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H).txt
        # Optional also run without density correction
        # python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind False  > ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H).txt
        python compute_generation.py ${scenario} ${realization} ${bc_realization} PV > ../logs/compute_generation_PV_log_$(date +%Y_%m_%d_%H).txt
        conda deactivate
        conda activate demand_ninja
        python compute_demand.py ${scenario} ${realization} ${bc_realization} > ../logs/compute_demand_log_$(date +%Y_%m_%d_%H).txt
        conda deactivate
      done
    done
done
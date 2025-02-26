#!/bin/bash
mkdir -p ../logs
for bc_realization in A B C
do
    conda activate CESM2energy
    python compute_bias_correction_prep.py ${bc_realization}  # Input files for bias correction
    conda deactivate
    for scenario in historical SSP245 SSP370
    do
      for realization in A B C
      do
        identifier=${scenario}_${realization}_${bc_realization}
        conda activate CESM2energy
        python compute_bias_correction.py ${scenario} ${realization} ${bc_realization} | tee ../logs/compute_bias_correction_log_$(date +%Y_%m_%d_%H)_${identifier}.txt
        python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind | tee ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H)_${identifier}.txt
        # Optional also run without density correction
        # python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind False  > ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H).txt
        python compute_generation.py ${scenario} ${realization} ${bc_realization} PV | tee ../logs/compute_generation_PV_log_$(date +%Y_%m_%d_%H)_${identifier}.txt
        conda deactivate
        conda activate demand_ninja
        python compute_demand.py ${scenario} ${realization} ${bc_realization} | tee ../logs/compute_demand_log_$(date +%Y_%m_%d_%H)_${identifier}.txt
        conda deactivate
        conda activate hydro
        python compute_hydro.py ${scenario} ${realization} ${bc_realization} | tee ../logs/compute_hydro_log_$(date +%Y_%m_%d_%H)_${identifier}.txt
        conda deactivate
      done
    done
done

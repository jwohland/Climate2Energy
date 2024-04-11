#!/bin/bash
mkdir -p ../logs
for bc_realization in A B C
do
    for scenario in historical SSP370
    do
      for realization in A B C
      do
        conda activate CESM2energy
        python compute_generation.py ${scenario} ${realization} ${bc_realization} > ../logs/compute_generation_log_$(date +%Y_%m_%d_%H).txt
        conda deactivate
        conda activate demand_ninja
        python compute_demand.py ${scenario} ${realization} ${bc_realization} > ../logs/compute_demand_log_$(date +%Y_%m_%d_%H).txt
        conda deactivate
      done
    done
done
#!/bin/bash
for bc_realization in A B C
do
    echo $bc_realization
    for scenario in historical SSP370
    do
      echo $scenario
      for realization in A B C
      do
        echo $realization
        conda activate CESM2energy
        python compute_generation.py ${scenario} ${realization} ${bc_realization}
        conda deactivate
        conda activate demand_ninja
        python compute_demand.py ${scenario} ${realization} ${bc_realization}
        conda deactivate
      done
    done
done
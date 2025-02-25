#!/bin/bash
mkdir -p ../logs
bc_realization=A 
scenario=SSP370
realization=A
#bias correction preparation
conda activate CESM2energy
python compute_bias_correction_prep.py ${bc_realization}  # Input files for bias correction
conda deactivate
for date in "2080-02-14" "2080-02-16" "2080-02-18" "2080-12-01" "2080-12-03" "2080-12-05" 
    do
    for ens in $(printf "%03d\n" {1..30})
      do
        input_path="/net/meso/climphys/cesm212/boosting/archive/BSSP370cmip6.0001500.${date}.ens${ens}/atm/hist/BSSP370cmip6.0001500.${date}.ens${ens}.cam.h6.${date}-03600.nc"
        input_path_discharge="/net/meso/climphys/cesm212/boosting/archive/BSSP370cmip6.0001500.${date}.ens${ens}/rof/hist/BSSP370cmip6.0001500.${date}.ens${ens}.mosart.h1.*-00000.nc"
        input_info="boost_${date}_ens${ens}"
        identifier=${scenario}_${realization}_${bc_realization}
        
        conda activate CESM2energy
        python compute_bias_correction.py ${scenario} ${realization} ${bc_realization} ${input_path} ${input_info} | tee ../logs/compute_bias_correction_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
        python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind ${input_info} | tee ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
        python compute_generation.py ${scenario} ${realization} ${bc_realization} PV ${input_info} | tee ../logs/compute_generation_PV_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
        conda deactivate
        
        conda activate demand_ninja
        python compute_demand.py ${scenario} ${realization} ${bc_realization} ${input_info}  tee ../logs/compute_demand_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
        conda deactivate
        
        conda activate hydro
        python compute_hydro.py ${scenario} ${realization} ${bc_realization} ${input_path_discharge} ${input_info} | tee ../logs/compute_hydro_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
        conda deactivate
      done
    done
done

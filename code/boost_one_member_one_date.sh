#!/bin/bash
set -eo pipefail

# ==============
# === inputs ===
# ==============

realization="$1"
bc_realization=${realization} #we use same bc realisation as the realisation itself
nb_realization="$2"
scenario="$3"
if [[ "$scenario" == "historical" ]]; then
    scenario="HIST" #get the right file naming convention
fi

year="$4"

date="$5"

ens=$(printf "%03d\n" "$6")

echo "${ens}"

# in and output paths
input_path_discharge="B${scenario}cmip6.100${nb_realization}.${date}.ens${ens}"
input_info="boost_${date}_ens${ens}"
output_path="/net/xenon/climphys/lbloin/CESM2energy/output/boost/${realization}/"
input_path="${output_path}/atmospheric_variables/atmospheric_variables_${date}_ens${ens}"

# compute 1st part of translation in CESM2energy env
conda activate CESM2energy
python compute_bias_correction.py ${scenario} ${realization} ${bc_realization} ${input_path} ${input_info} ${year} ${output_path} True | tee ../logs/compute_bias_correction_log_$(date +%Y_%m_%d_%H)_${input_info}.txt
python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind ${input_info} True ${output_path} | tee ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H)_${input_info}.txt
python compute_generation.py ${scenario} ${realization} ${bc_realization} PV ${input_info} True ${output_path} | tee ../logs/compute_generation_PV_log_$(date +%Y_%m_%d_%H)_${input_info}.txt
conda deactivate

# compute 2nd part of translation in demand_ninja env
conda activate demand_ninja
python compute_demand.py ${scenario} ${realization} ${bc_realization} ${input_info} ${output_path} | tee ../logs/compute_demand_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
conda deactivate

# compute 3rd part of translation in hydro env
conda activate hydro
python compute_hydro.py  ${input_path_discharge} ${input_info} ${output_path} CESM2 ${bc_realization} | tee ../logs/compute_hydro_log_$(date +%Y_%m_%d_%H)_${identifier}${input_info}.txt
conda deactivate

echo "${date} member ${ens} fully translated"



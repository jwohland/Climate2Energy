#!/bin/bash
bc_realization=A 
scenario=SSP370
realization=A

chain="MOHC-HadREM3-GA7-05_MOHC-HadGEM2-ES" #"MOHC-HadREM3-GA7-05_ICHEC-EC-EARTH"
output_path="../output/CORDEX_data/${chain}/"
input_info="CORDEX_${chain}"

# preprocessing
echo "preprocessing all CORDEX data"
conda activate iacpy3_2024
python preprocess_cordex.py
conda deactivate
echo "preprocessing done"

#compute demand
echo "convert demand"
conda activate demand_ninja
for rcp in 26 85
do
	python compute_demand.py ${scenario} ${realization} ${bc_realization} ${input_info}_${rcp} ${output_path} ${input_info} tee ../logs/compute_demand_log_$(date +%Y_%m_%d_%H)_${input_info}_${rcp}.txt
done
echo "demand done"
conda deactivate
        
conda activate hydro
for rcp in 26 85
do
	for time_range in 1991-1995 1996-2000 2001-2005 2006-2010 2011-2015 2016-2020 2021-2025 2026-2030 2031-2035 2036-2040 2041-2045 2046-2050 2051-2055 2056-2060 
	do
		echo ${time_range}
		python compute_hydro.py  ${output_path} ${input_info}_${time_range}_${rcp} ${output_path} ${input_info} | tee ../logs/compute_hydro_log_$(date +%Y_%m_%d_%H)_${input_info}_${rcp}.txt
		echo "discharge done"
	done
done
conda deactivate
 

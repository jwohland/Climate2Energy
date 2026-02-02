#!/bin/bash
set -o pipefail

# ==============
# === INPUTS ===
# ==============

realization="A"
scenario="SSP370"
year="2080"
dates=(
  "2080-02-14"
  "2080-02-16"
  "2080-02-18"
  "2080-12-01"
  "2080-12-03"
  "2080-12-05"
)
members=10
# get the correct realization number for file naming convention
conda activate iacpy3_2024
nb_realization=$(python3 - <<EOF
from utils import CESM2_REALIZATION_DICT
print(CESM2_REALIZATION_DICT["$scenario"]["$realization"])
EOF
)
conda deactivate

# How many parallel jobs at once?
PARALLEL_JOBS=${members}	

# run boost_one_date_one_member for different dates and members
for date in "${dates[@]}"; do
	echo "${realization} ${nb_realization} ${scenario} ${year} ${date}"
	parallel -j ${PARALLEL_JOBS} bash -l boost_one_member_one_date.sh ${realization} ${nb_realization} ${scenario} ${year} ${date} ::: $(seq 1 "${members}")

done


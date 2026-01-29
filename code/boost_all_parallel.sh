#!/bin/bash
set -o pipefail

# ==============
# === INPUTS ===
# ==============

realization="B"
scenario="historical"
year="1996"
dates=(
  "1996-01-20"
  "1996-01-23"
  "1996-01-26"
  "1996-01-29"
  "1996-02-01"
)

# get the correct realization number for file naming convention
conda activate iacpy3_2024
nb_realization=$(python3 - <<EOF
from utils import CESM2_REALIZATION_DICT
print(CESM2_REALIZATION_DICT["$scenario"]["$realization"])
EOF
)
conda deactivate

# How many parallel jobs at once?
PARALLEL_JOBS=50	

# run boost_one_date_one_member for different dates and members
for date in "${dates[@]}"; do
	echo "${realization} ${nb_realization} ${scenario} ${year} ${date}"
	parallel -j ${PARALLEL_JOBS} bash -l boost_one_member_one_date.sh ${realization} ${nb_realization} ${scenario} ${year} ${date} ::: {1..50}

done


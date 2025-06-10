#!/bin/bash

realization=A

bc_realization=A

for scenario in historical SSP370

    do

    identifier=${scenario}_${realization}_${bc_realization}



    # Optional also run without density correction

    python compute_generation.py ${scenario} ${realization} ${bc_realization} Wind False  >  ../logs/compute_generation_wind_log_$(date +%Y_%m_%d_%H).txt



done

#!/bin/bash
for year in 2016 2017 2018
do
    echo $year
    python3 run_all.py $year
done
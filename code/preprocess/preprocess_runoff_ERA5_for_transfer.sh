# needs to be executed as preprocess/preprocess_runoff_ERA5

for i in {2017..2022}
    do
    # calculate daily average (era5 runoff is in units of m, no time unit), remap (conservative) to CESM grid, select Europe, change to fit mm/d
    cdo -b F32 -setattribute,runoff@units="mm/d" -mulc,1000 -selname,runoff -chname,ro,runoff -sellonlatbox,-15,50,30,75 -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/original/era5_deterministic_recent.ro.025deg.1h."${i}".nc ../output/tmp_"${i}"_runoff.nc

done

cdo mergetime ../output/tmp_*_runoff.nc ../output/runoff_ERA5_2017-2022.nc

rm ../output/tmp_*_runoff.nc

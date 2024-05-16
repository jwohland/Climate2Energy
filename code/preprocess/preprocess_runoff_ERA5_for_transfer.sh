# needs to be executed as preprocess/preprocess_runoff_ERA5_for_transfer

for i in {2015..2023}
    do
    # calculate daily average (era5 runoff is in units of m, no time unit), remap (conservative) to CESM grid, select Europe, change to fit mm/d
    cdo -b F32 -setattribute,runoff@units="mm/d" -mulc,1000 -sellonlatbox,-15,50,30,75 -selname,runoff -chname,ro,runoff -daysum -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/original/era5_deterministic_recent.ro.025deg.1h."${i}".nc ../output/tmp_"${i}"_runoff.nc

done

cdo mergetime ../output/tmp_*_runoff.nc ../output/runoff_ERA5_2015_2023.nc

rm ../output/tmp_*_runoff.nc

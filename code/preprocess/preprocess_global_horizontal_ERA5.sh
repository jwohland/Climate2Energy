# needs to be executed as preprocess/preprocess_global_horizontal_ERA5
for i in {1981..2010}
    do
    # remap (conservative) to CESM grid, select Europe, change name to temperature, convert to W/m2 (with units)
    cdo -b F64 -divc,3600 -setattribute,global_horizontal@units="W/m^2" -dayavg -chname,ssrd,global_horizontal -sellonlatbox,-15,50,30,75 -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/era5_deterministic_recent.ssrd.025deg.1h."${i}".nc ../output/tmp_"${i}"_global_horizontal.nc

done

cdo mergetime ../output/tmp_*_global_horizontal.nc ../output/global_horizontal_ERA5.nc

rm ../output/tmp_*_global_horizontal.nc

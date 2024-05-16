# needs to be executed as preprocess/preprocess_discharge_ERA5

for i in {1..9} #{2021..2023}
    do
    # remap (conservative) to CESM grid, select Europe
    cdo -sellonlatbox,-15,50,30,75 -selname,discharge -chname,dis24,discharge -remapcon,../inputs/CESM_clm_grid.txt /net/xenon/climphys/lbloin/energy_boost/data_"${i}".nc ../output/tmp_"${i}"_discharge.nc #atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/original/era5_deterministic_recent.ro.025deg.1h."${i}".nc ../output/tmp_"${i}"_runoff.nc #

done

cdo mergetime ../output/tmp_*_discharge.nc ../output/discharge_ERA5_2015_2023.nc

rm ../output/tmp_*_discharge.nc

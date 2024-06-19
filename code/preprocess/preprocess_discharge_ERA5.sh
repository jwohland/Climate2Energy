# needs to be executed as preprocess/preprocess_discharge_ERA5

for i in {1995..2014}
    do
    # remap (conservative) to CESM grid, rename and select discharge, select Europe
    cdo -sellonlatbox,-15,50,30,75 -selname,discharge -chname,dis24,discharge -remapcon,../inputs/CESM_clm_grid.txt /net/xenon/climphys/lbloin/CESM2energy_data/ERA5_discharge/discharge_"${i}".nc ../output/tmp_"${i}"_discharge.nc
done

cdo mergetime ../output/tmp_*_discharge.nc ../output/discharge_ERA5.nc

rm ../output/tmp_*_discharge.nc

# needs to be executed as preprocess/preprocess_discharge_ERA5

for i in {2015..2023}
    do
    # remap (conservative) to CESM grid, select Europe
    cdo -sellonlatbox,-15,50,30,75 -selname,discharge -chname,dis24,discharge -remapcon,../inputs/CESM_clm_grid.txt /net/xenon/climphys/lbloin/CESM2energy_data/ERA5_discharge/discharge_"${i}".nc ../output/tmp_"${i}"_discharge.nc 
done

cdo mergetime ../output/tmp_*_discharge.nc ../output/discharge_ERA5_2015_2023.nc

rm ../output/tmp_*_discharge.nc

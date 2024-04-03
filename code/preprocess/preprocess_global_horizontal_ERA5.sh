# needs to be executed as preprocess/preprocess_global_horizontal_ERA5
output_path=../output/bias_correction
input_path_ERA5=/net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/

for year in {1995..2014}
    do
    # remap (conservative) to CESM grid, select Europe, change name to global_horizontal, convert to W/m2 (with units)
    cdo -b F64 -divc,3600 -setattribute,global_horizontal@units="W/m^2" -chname,ssrd,global_horizontal -sellonlatbox,-15,50,30,75 -remapcon,../inputs/CESM_atm_grid.txt ${input_path_ERA5}/era5_deterministic_recent.ssrd.025deg.1h."${year}".nc ${output_path}/tmp_"${year}"_global_horizontal_ERA5.nc

done

cdo mergetime ${output_path}/tmp_*_global_horizontal_ERA5.nc ${output_path}/Raw_ERA5_global_horizontal.nc

rm ${output_path}/tmp_*_global_horizontal_ERA5.nc

# needs to be executed as preprocess/preprocess_temperature_ERA5
output_path=../output/bias_correction

for year in {1995..2014}
    do
    # calculate daily average, remap (bilinear) to CESM grid, select Europe, change name to temperature, convert to celsius
    cdo -b F32 -addc,-273.15 -setattribute,temperature@units="°C" -chname,t2m,temperature -sellonlatbox,-15,50,30,75 -remapbil,../inputs/CESM_atm_grid.txt /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/era5_deterministic_recent.t2m.025deg.1h."${year}".nc ${output_path}/tmp_"${year}"_temperature_ERA5.nc

done

cdo mergetime ${output_path}/tmp_*_temperature_ERA5.nc ${output_path}/Raw_ERA5_temperature.nc

rm ${output_path}/tmp_*_temperature_ERA5.nc


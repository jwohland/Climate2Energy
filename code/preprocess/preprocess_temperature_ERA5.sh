# needs to be executed as preprocess/preprocess_temperature_ERA5
output_path=../output/bias_correction

for year in {1995..2014}
    do
    # The following cdo comment is split into multiple lines to increase legibility. Here is what happens per line
    # 1) Convert from Kelvin to Celsius
    # 2) rename from t2m to temperature
    # 3) Choose European region of interest
    # 4) Remap bilinearly to CESM2 grid
    # 5) Choose region with 5 degrees sponge in all directions (just to speed up computation)
    # 6) ERA5 input file
    # 7) output file
    cdo -b F32 -addc,-273.15 -setattribute,temperature@units="°C" \
    -chname,t2m,temperature \
    -sellonlatbox,-15,50,30,75 \
    -remapbil,../inputs/CESM_atm_grid.txt \
    -sellonlatbox,-20,55,25,80 \
    /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/era5_deterministic_recent.t2m.025deg.1h.${year}.nc \
    ${output_path}/tmp_${year}_temperature_ERA5.nc
done
# merge all years
cdo mergetime ${output_path}/tmp_*_temperature_ERA5.nc ${output_path}/Raw_ERA5_temperature.nc
# clean up
rm ${output_path}/tmp_*_temperature_ERA5.nc
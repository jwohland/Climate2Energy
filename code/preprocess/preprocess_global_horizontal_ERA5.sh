# needs to be executed as preprocess/preprocess_global_horizontal_ERA5
output_path=../output/bias_correction
input_path_ERA5=/net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/

for year in {1995..2014}
    do
    # The following cdo comment is split into multiple lines to increase legibility. Here is what happens per line
    # 1) Unit conversion to W/m2
    # 2) rename from ssrd to global_horizontal
    # 3) Choose European region of interest
    # 4) Remap conservatively to CESM2 grid
    # 5) Choose region with 5 degrees sponge in all directions (just to speed up computation)
    # 6) ERA5 input file
    # 7) output file
    cdo -b F64 -divc,3600 -setattribute,global_horizontal@units="W/m^2" \
    -chname,ssrd,global_horizontal \
    -sellonlatbox,-15,50,30,75 \
    -remapcon,../inputs/CESM_atm_grid.txt \
    -sellonlatbox,-20,55,25,80 \
    ${input_path_ERA5}/era5_deterministic_recent.ssrd.025deg.1h."${year}".nc \
    ${output_path}/tmp_"${year}"_global_horizontal_ERA5.nc
done
# merge all years
cdo mergetime ${output_path}/tmp_*_global_horizontal_ERA5.nc ${output_path}/Raw_ERA5_global_horizontal.nc
# clean up
rm ${output_path}/tmp_*_global_horizontal_ERA5.nc

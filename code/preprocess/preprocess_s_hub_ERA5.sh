# needs to be executed as preprocess/preprocess_s_hub_ERA5
output_path=../output/bias_correction
input_path_ERA5=/net/atmos/data/era5_cds/original

for year in {1995..2014}
    do
    for month in 01 02 03 04 05 06 07 08 09 10 11 12
        do
        #select Europe + 5 degrees sponge, monthly to yearly, change name to U
        cdo sellonlatbox,-20,55,25,80 -mergetime -chname,100u,U ${input_path_ERA5}/100u/1hr/${year}/100u_1hr_era5_${year}${month}.nc ${output_path}/u_${year}${month}.nc
        #same for V
        cdo sellonlatbox,-20,55,25,80 -mergetime -chname,100v,V ${input_path_ERA5}/100v/1hr/${year}/100v_1hr_era5_${year}${month}.nc ${output_path}/v_${year}${month}.nc
        # add U an V to same file
        cdo merge ${output_path}/u_${year}${month}.nc ${output_path}/v_${year}${month}.nc ${output_path}/tmp_${year}${month}_s_hub_uv.nc
        # calculate s = sqrt(u^2 + v^2), select only s, remap (bilinearly), select Europe
        cdo sellonlatbox,-15,50,30,75 -remapbil,../inputs/CESM_atm_grid.txt -selname,s_hub -expr,"s_hub=sqrt(U*U+V*V);" ${output_path}/tmp_${year}${month}_s_hub_uv.nc ${output_path}/tmp_${year}${month}_s_hub.nc
        # delete intermediate files
        rm ${output_path}/u_${year}${month}.nc
        rm ${output_path}/v_${year}${month}.nc
        rm ${output_path}/tmp_${year}${month}_s_hub_uv.nc
        done
done
# merge all years
cdo mergetime ${output_path}/tmp_*_s_hub.nc ${output_path}/Raw_ERA5_s_hub.nc
# clean up
rm ${output_path}/tmp_*_s_hub.nc
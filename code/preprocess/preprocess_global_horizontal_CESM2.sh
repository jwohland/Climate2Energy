# needs to be executed as preprocess/preprocess_global_horizontal_CESM2 bc_realization CESM2_realization
bc_realization=$1  # name of CESM2 realization used in bias correction. Options: A,B,C
CESM2_realization=$2  # Number of CESM2 realization used in bias corrected. This is linked to above as: A: 1500, B: 1000, C: 1200

CESM2_path=/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}/archive/atm/hist
output_path=../output/bias_correction/${bc_realization}

for year in {1995..2014}
    do
    # Following CDO statement is split into multiple lines. Here is what happens per line:
    # 1) Select Europe
    # 2) Select FSDS and rename to global_horizontal
    # 3) CESM input file
    # 4) output file name
    cdo -sellonlatbox,-15,50,30,75 \
    -chname,FSDS,global_horizontal -selname,FSDS \
    ${CESM2_path}/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}.cam.h6.${year}-01-01-03600.nc \
    ${output_path}/global_horizontal_${year}_mod.nc
done
# Combine all years
cdo -mergetime ${output_path}/global_horizontal_*_mod.nc ${output_path}/Raw_CESM2_global_horizontal_${bc_realization}.nc
# Clean up
rm ${output_path}/global_horizontal_*_mod.nc
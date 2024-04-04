# needs to be executed as preprocess/preprocess_s_hub_CESM2 bc_realization CESM2_realization
bc_realization=$1  # name of CESM2 realization used in bias correction. Options: A,B,C
CESM2_realization=$2  # Number of CESM2 realization used in bias corrected. This is linked to above as: A: 1500, B: 1000, C: 1200

CESM2_path=/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}/archive/atm/hist
output_path=../output/bias_correction/${bc_realization}

for year in {1995..2014}
    do
    # Following CDO statement is split into multiple lines. Here is what happens per line:
    # 1) Compute wind speed from wind components and call it S
    # 2) Select Europe
    # 3) Select two lowermost model levels 31 & 32 (CESM2 counts downwards from top of atmosphere)
    # 3) CESM input file
    # 4) output file name
    # select lowest level (32 because cdo starts at 1), select Europe, calculate s = sqrt(u2+v2), select just s
    cdo -selname,S -expr,"S=sqrt(U*U+V*V);" \
    -sellonlatbox,-15,50,30,75 \
    -sellevidx,31,32 \
    ${CESM2_path}/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}.cam.h6.${year}-01-01-03600.nc \
    ${output_path}/s_hub_${year}_mod.nc
    # similarly for Z3:
    # 1) Select geopotential Z3
    # 2) Select two lowermost model levels
    # 3) CESM2 input file
    # 4) Output file name
    cdo -selvar,Z3  \
    -sellonlatbox,-15,50,30,75 \
    -sellevidx,31,32 \
    ${CESM2_path}/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}.cam.h6.${year}-01-01-03600.nc \
    ${output_path}/Z3_${year}_mod.nc
done
# Combine all years
cdo -mergetime ${output_path}/s_hub_*_mod.nc ${output_path}/Raw_CESM2_s_hub_${bc_realization}.nc
cdo -mergetime ${output_path}/Z3_*_mod.nc ${output_path}/Raw_CESM2_Z3_${bc_realization}.nc
# Clean up
rm ${output_path}/s_hub_*_mod.nc
rm ${output_path}/Z3_*_mod.nc



 
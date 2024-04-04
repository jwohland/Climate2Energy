# needs to be executed as preprocess/preprocess_temperature_CESM2
bc_realization=$1  # name of CESM2 realization used in bias correction. Options: A,B,C
CESM2_realization=$2  # Number of CESM2 realization used in bias corrected. This is linked to above as: A: 1500, B: 1000, C: 1200

CESM2_path=/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}/archive/atm/hist
output_path=../output/bias_correction/${bc_realization}

for year in {1995..2014}
    do
    # select Europe, select just TREFHT, change name to temperature, convert to celsius
    # Following CDO statement is split into multiple lines. Here is what happens per line:
    # 1) Convert from Kelvin to Celsius
    # 2) Select TREFHT and rename to temperature
    # 3) Select Europe
    # 4) CESM input file
    # 5) output path and file name
    cdo -addc,-273.15 -setattribute,temperature@units="°C" \
    -chname,TREFHT,temperature -selname,TREFHT \
    -sellonlatbox,-15,50,30,75 \
    ${CESM2_path}/b.e212.BHISTcmip6.f09_g17.${CESM2_realization}.cam.h6.${year}-01-01-03600.nc \
    ${output_path}/temperature_${year}_mod.nc
done
# Combine all years
cdo -mergetime ${output_path}/temperature_*_mod.nc ${output_path}/Raw_CESM2_temperature_${bc_realization}.nc
# Clean up
rm ${output_path}/temperature_*_mod.nc
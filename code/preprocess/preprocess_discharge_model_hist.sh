# needs to be executed as preprocess/preprocess_discharge_model_hist

# taking one ensemble member (1500) of CESM2 data and mergeing them into one file that fits our input needs
for year in {1990..2015}
    do
    for month in 01 02 03 04 05 06 07 08 09 10 11 12
        do
        # select Europe, select just discharge
        cdo -selname,discharge -chname,RIVER_DISCHARGE_OVER_LAND_LIQ,discharge -sellonlatbox,-15,50,30,75 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/rof/hist/b.e212.BHISTcmip6.f09_g17.1500.mosart.h0.${year}-${month}.nc ../output/discharge_${year}_${month}_mod.nc
    done
done
#do the summing up here since otherwise the mergetime gives double values for every jan 1
cdo mergetime ../output/discharge_*_mod.nc ../output/hist_discharge.nc
rm ../output/discharge_*_mod.nc
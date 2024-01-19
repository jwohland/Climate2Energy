# needs to be executed as preprocess/preprocess_global_horizontal_model_hist

# taking one ensemble member (1500) of CESM2 data and mergeing them into one file that fits our input needs
for year in {1990..2010}
    do
    # select Europe, select just FSDS, change name to global horizontal
    cdo -chname,FSDS,global_horizontal -sellonlatbox,-15,50,30,75 -selname,FSDS /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.1500.cam.h6.${year}-01-01-03600.nc ../output/global_horizontal_${year}_mod.nc


done

cdo -mergetime ../output/global_horizontal_*_mod.nc ../output/hist_global_horizontal.nc
rm ../output/global_horizontal_*_mod.nc
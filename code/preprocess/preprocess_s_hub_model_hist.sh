# needs to be executed as preprocess/preprocess_s_hub_model_hist

# taking one ensemble member (0900) of CESM2 data and mergeing them into one file that fits our input needs
for year in {1981..2010}
    do
    # select lowest level (32 because cdo starts at 1), select Europe, calculate s = sqrt(u2+v2), select just s
    cdo -selname,S -expr,"S=sqrt(U*U+V*V);" -sellonlatbox,-15,50,30,75 -sellevidx,31,32 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.0900/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.0900.cam.h3.${year}-01-01-00000.nc ../output/s_hub_${year}_mod.nc
    #the same for Z3
    cdo -selvar,Z3  -sellonlatbox,-15,50,30,75 -sellevidx,31,32 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.0900/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.0900.cam.h3.${year}-01-01-00000.nc ../output/Z3_${year}_mod.nc
    
done

cdo -mergetime ../output/s_hub_*_mod.nc ../output/hist_s_hub.nc
rm ../output/s_hub_*_mod.nc

cdo -mergetime ../output/Z3_*_mod.nc ../output/hist_Z3.nc
rm ../output/Z3_*_mod.nc



 
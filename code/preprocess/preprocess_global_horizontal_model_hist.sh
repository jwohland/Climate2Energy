# taking one ensemble member (0900) of CESM2 data and mergeing them into one file that fits our input needs
for year in {1981..2010}
    do
    # select Europe, select just FSDS, change name to global horizontal
    cdo -chname,FSDS,global_horizontal -sellonlatbox,-15,50,30,75 -selname,FSDS /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.0900/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.0900.cam.h2.${year}-01-01-00000.nc /net/xenon/climphys/lbloin/energy_boost/global_horizontal_${year}_mod.nc
    
done

cdo -mergetime /net/xenon/climphys/lbloin/energy_boost/global_horizontal_*_mod.nc ../../output/hist_global_horizontal.nc
rm /net/xenon/climphys/lbloin/energy_boost/global_horizontal_*_mod.nc
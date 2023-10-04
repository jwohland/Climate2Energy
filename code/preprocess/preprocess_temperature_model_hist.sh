# taking one ensemble member (0900) of CESM2 data and mergeing them into one file that fits our input needs
for year in {1981..2010}
    do
    # select Europe, select just TREFHT, change name to temperature, convert to celsius
    cdo -addc,-273.15 -setattribute,temperature@units="°C" -chname,TREFHT,temperature -selname,TREFHT -sellonlatbox,-15,50,30,75 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.0900/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.0900.cam.h1.${year}-01-01-00000.nc ../../output/temperature_${year}_mod.nc
    
done

cdo -mergetime ../../output/temperature_*_mod.nc ../../output/hist_temperature.nc
rm ../../output/temperature_*_mod.nc
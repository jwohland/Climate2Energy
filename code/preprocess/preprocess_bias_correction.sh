#!/bin/bash


### === REGRIDDING ERA5 ===
for i in {1981..2010}
    do
    #temperature (remapbil)
    cdo -chname,t2m,temperature -sellonlatbox,-15,50,30,75 -remapbil,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt -dayavg -selvar,t2m /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/era5_deterministic_recent.t2m.025deg.1h."${i}".nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_temperature.nc

    #solar flux (remapcon)
    cdo -chname,ssrd,FSDS -sellonlatbox,-15,50,30,75 -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt -mulc,0.0002777777777777777777777777777778 -dayavg -selname,ssrd /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/era5_deterministic_recent.ssrd.025deg.1h."${i}".nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_FSDS.nc

    #wind s sqrt(u2+v2) 100 m wind speed!
    cdo -mergetime -chname,100u,U /net/atmos/data/era5_cds/original/100u/1hr/"${i}"/100u_1hr_era5_"${i}"*.nc /net/xenon/climphys/lbloin/energy_boost/u_"${i}".nc

    cdo -mergetime -chname,100v,V /net/atmos/data/era5_cds/original/100v/1hr/"${i}"/100v_1hr_era5_"${i}"*.nc /net/xenon/climphys/lbloin/energy_boost/v_"${i}".nc

    cdo merge /net/xenon/climphys/lbloin/energy_boost/u_${i}.nc /net/xenon/climphys/lbloin/energy_boost/v_${i}.nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub_uv.nc

    cdo -sellonlatbox,-15,50,30,75 -timselmean,6 -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt -selname,s_hub -expr,"s_hub=sqrt(U*U+V*V);" /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub_uv.nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub.nc
    
    rm /net/xenon/climphys/lbloin/energy_boost/u_"${i}".nc
    rm /net/xenon/climphys/lbloin/energy_boost/v_"${i}".nc
    rm /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub_uv.nc

done

# merge and delete temporary files for all three variables
for var in temperature FSDS s_hub
    do
    cdo mergetime /net/xenon/climphys/lbloin/energy_boost/tmp_*_${var}.nc ../output/${var}_ERA5.nc
done

rm /net/xenon/climphys/lbloin/energy_boost/tmp_*.nc

# # === CONCATENATING HISTORICAL MODEL DATA ===

for mem in 0900 #1000 1100 1200 1300 1400 1500 todo: add all members
    do

    for year in {1981..2010}
        do
        # temperature
        cdo -addc,-273.15 -chname,TREFHT,temperature -selname,TREFHT -sellonlatbox,-15,50,30,75 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.${mem}/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.${mem}.cam.h1.${year}-01-01-00000.nc /net/xenon/climphys/lbloin/energy_boost/temperature_${mem}_${year}.nc

        # solar flux
        cdo -sellonlatbox,-15,50,30,75 -selname,FSDS /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.${mem}/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.${mem}.cam.h2.${year}-01-01-00000.nc /net/xenon/climphys/lbloin/energy_boost/FSDS_${mem}_${year}.nc
        
        # wind
        cdo -selname,s_hub -expr,"s_hub=sqrt(U*U+V*V);" -sellonlatbox,-15,50,30,75  -sellevidx,31 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.${mem}/archive/atm/hist/b.e212.BHISTcmip6.f09_g17.${mem}.cam.h3.${year}-01-01-00000.nc /net/xenon/climphys/lbloin/energy_boost/s_hub_${mem}_${year}.nc    

    done

    # merge files for all three variables and delete temporary output
    for var in temperature FSDS s_hub
        do
        #time
        cdo mergetime /net/xenon/climphys/lbloin/energy_boost/${var}_${mem}_*.nc /net/xenon/climphys/lbloin/energy_boost/${var}_${mem}.nc
        rm /net/xenon/climphys/lbloin/energy_boost/${var}_${mem}_*.nc
    done 
done
 

for var in temperature FSDS s_hub
    do
    #by member
    cdo -merge /net/xenon/climphys/lbloin/energy_boost/${var}_*.nc ../output/hist_${var}.nc
    rm /net/xenon/climphys/lbloin/energy_boost/${var}_*.nc
done 


exit 0
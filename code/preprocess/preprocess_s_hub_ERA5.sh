for i in {1981..2010}
    do
    #monthly to yearly file, change name to U
    cdo -mergetime -chname,100u,U /net/atmos/data/era5_cds/original/100u/1hr/"${i}"/100u_1hr_era5_"${i}"*.nc /net/xenon/climphys/lbloin/energy_boost/u_"${i}".nc
    #monthly to yearly file, change name to V
    cdo -mergetime -chname,100v,V /net/atmos/data/era5_cds/original/100v/1hr/"${i}"/100v_1hr_era5_"${i}"*.nc /net/xenon/climphys/lbloin/energy_boost/v_"${i}".nc
    # add U an V to same file
    cdo merge /net/xenon/climphys/lbloin/energy_boost/u_${i}.nc /net/xenon/climphys/lbloin/energy_boost/v_${i}.nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub_uv.nc
    # calculate s = sqrt(u^2 + v^2), select only s, remap (conservative), calculate 6-hourly mean, select Europe TODO: insta values
    cdo -sellonlatbox,-15,50,30,75 -selhour,0,6,12,18 -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt -selname,s_hub -expr,"s_hub=sqrt(U*U+V*V);" /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub_uv.nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub.nc
    
    rm /net/xenon/climphys/lbloin/energy_boost/u_"${i}".nc
    rm /net/xenon/climphys/lbloin/energy_boost/v_"${i}".nc
    rm /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_s_hub_uv.nc

done
# merge all years
cdo mergetime /net/xenon/climphys/lbloin/energy_boost/tmp_*_s_hub.nc ../../output/s_hub_ERA5.nc

rm /net/xenon/climphys/lbloin/energy_boost/tmp_*_s_hub.nc
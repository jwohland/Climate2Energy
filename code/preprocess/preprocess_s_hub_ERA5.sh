# needs to be executed as preprocess/preprocess_s_hub_ERA5

for i in {1990..2010}
    do
    #monthly to yearly file, change name to U
    cdo -chname,100u,U -sellonlatbox,-15,50,30,75 -mergetime  /net/atmos/data/era5_cds/original/100u/1hr/"${i}"/100u_1hr_era5_"${i}"*.nc ../output/u_"${i}".nc
    #monthly to yearly file, change name to V
    cdo -chname,100v,V -sellonlatbox,-15,50,30,75 -mergetime /net/atmos/data/era5_cds/original/100v/1hr/"${i}"/100v_1hr_era5_"${i}"*.nc ../output/v_"${i}".nc
    # add U an V to same file
    cdo -merge ../output/u_${i}.nc ../output/v_${i}.nc ../output/tmp_"${i}"_s_hub_uv.nc
    
    rm ../output/u_"${i}".nc
    rm ../output/v_"${i}".nc
   
    # calculate s = sqrt(u^2 + v^2), select only s, remap (conservative), calculate 6-hourly mean, select Europe TODO: insta values
    cdo -remapcon,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt -selname,s_hub -expr,"s_hub=sqrt(U*U+V*V);" ../output/tmp_"${i}"_s_hub_uv.nc ../output/tmp_"${i}"_s_hub.nc
    

    rm ../output/tmp_"${i}"_s_hub_uv.nc

done
# merge all years
cdo mergetime ../output/tmp_*_s_hub.nc ../output/s_hub_ERA5.nc

rm ../output/tmp_*_s_hub.nc
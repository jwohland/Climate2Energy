for i in {1981..2010}
    do
    # calculate daily average, remap (bilinear) to CESM grid, select Europe, change name to temperature, convert to celsius
    cdo -b F32 -addc,-273.15 -setattribute,temperature@units="°C" -chname,t2m,temperature -sellonlatbox,-15,50,30,75 -remapbil,/net/meso/climphys/flehner/observations/era5/day/CESM_atm_grid.txt -dayavg /net/atmos/data/ERA5_deterministic/recent/0.25deg_lat-lon_1h/processed/regrid/era5_deterministic_recent.t2m.025deg.1h."${i}".nc /net/xenon/climphys/lbloin/energy_boost/tmp_"${i}"_temperature.nc

done

cdo mergetime /net/xenon/climphys/lbloin/energy_boost/tmp_*_temperature.nc ../../output/temperature_ERA5.nc

rm /net/xenon/climphys/lbloin/energy_boost/tmp_*_temperature.nc


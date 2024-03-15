# needs to be executed as preprocess/preprocess_runoff_model_hist

# taking one ensemble member (1500) of CESM2 data and mergeing them into one file that fits our input needs
for year in {1990..2015}
    do
    # select Europe, select just runoff, change to be in mm/d (the original file is in mm/s - mm/d = (mm/s)*3600*24, since the files are hourly, we multiply by 3600 and sum up over the day)
    cdo -selname,runoff -chname,QRUNOFF,runoff -sellonlatbox,-15,50,30,75 /net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/lnd/hist/b.e212.BHISTcmip6.f09_g17.1500.clm2.h6.${year}-01-01-03600.nc ../output/runoff_${year}_mod.nc


done
#do the summing up here since otherwise the mergetime gives double values for every jan 1
cdo setattribute,runoff@units="mm/d" -daysum -mulc,3600 -mergetime ../output/runoff_*_mod.nc ../output/hist_runoff.nc
rm ../output/runoff_*_mod.nc
from bias_correction_methods import bias_correct_hydro
from utils import store_as_pandas_dataframe
from conversion_to_hydro import *
import sys
import xarray as xr
import pandas as pd
import numpy as np

if __name__ == "__main__":
    # parameters
    scenario = sys.argv[1]
    realization = sys.argv[2]
    bc_realization = sys.argv[3]

    technologies = ["ror","inflow"]
    rolling = {"ror":21,"inflow":3} # time to roll over - since inflow is weekly 3 weeks = 21 days
    
    # =====================================================
    # === Step 1: Open, bias correct and aggregate data ===
    # =====================================================
    
    # === CESM2 discharge === 
    print("Open CESM2 and ERA5 discharge")
    # open CESM2 discharge
    discharge_full = open_discharge(scenario, realization)
    # open CESM2 discharge HIST, for bias correction
    discharge_full_for_bc = open_discharge("historical", bc_realization)
    # opening ERA5 discharge for 1995-2015, for bias correction and for 2016-2023 for run-of-river calibration
    era5_discharge_full = open_era(discharge_full.lat,discharge_full.lon) 
    print("Bias correct CESM2")
    # Bias correction
    discharge_full = bias_correct_hydro(discharge_full.discharge, 
                                        era5_discharge_full.sel(time=slice("1995","2014")).discharge.load(), 
                                        discharge_full_for_bc.discharge
                                       ).to_dataset(name="discharge").convert_calendar("proleptic_gregorian") # to get numpy datetime (necessary for weekly resampling)
    # save bias corrected discharge, year for year
    for year in get_time_range(scenario):
        discharge_full.sel(time="year").to_netcdf(f"../output/bias_correction/{bc_realization}/{scenario}/{realization}/atmospheric_variables/bced_CESM2_discharge_{year}.nc")
    # aggregation
    for tech in technologies:
        print(f"Aggregate CESM2 and ERA5 for tech {tech}")
        discharge = weighted_aggregation(discharge_full,tech).discharge
        era5_discharge = weighted_aggregation(era5_discharge_full,tech)
        
        # === calibration data (ENTSO-e and ERA5 (2016-2023) === 
        print(f"Open ENTSO-e data for tech {tech}")
        # ENTSO-e
        calibration_ds = open_entsoe(tech) # conversion data set for inflows/ror
        [start,end] = calibration_ds.groupby("time.year").sum().year[[0,-1]].values
        era_discharge_for_calibration = era5_discharge.sel(time=slice(str(start),str(end)))["discharge"].sel(country=calibration_ds.country) #for calibration, we only use the years available from ENTSO-e for ERA5
        if tech == "inflow":
            time_range = calibration_ds.time[[0,-1]].values # find values of start and end date, to open era5 weekly correctly
            era_discharge_for_calibration = open_weekly(era_discharge_for_calibration,time_range=time_range) # get era5 in weekly resolution
            discharge = open_weekly(discharge) # get cesm2 in weekly resolution
        if tech =="ror":
            era_discharge_for_calibration["time"] = calibration_ds.time #ensuring same time stamp (discharge resamples to 11.30 every day and not 00.00)
        calibration_ds["discharge"] = era_discharge_for_calibration
    
        # rolling means
        discharge = discharge.rolling(time=rolling[tech],center=True).mean().load()
        calibration_ds = calibration_ds.rolling(time=rolling[tech],center=True).mean().load()
        # make sure that only countries present in calibration_ds are present in discharge
        discharge = discharge.sel(country=calibration_ds.country)
    
        print(f"All {tech} files opened and preprocessed. Conversion starting")
    
        # =====================================
        # === Step 2: Convert to hydropower ===
        # =====================================     
        transferred = []
        for country in discharge.country.values:
            [a1_opt, b1_opt, a2_opt, b2_opt], q =  get_pwlf(calibration_ds.sel(country=country).dropna(dim="time"),tech)
            transferred.append(piecewise_linear(
                                                discharge.sel(country=country).values, 
                                                a1_opt, 
                                                b1_opt,
                                                a2_opt, 
                                                b2_opt,
                                                q
                                            )
                              )
        transferred = xr.DataArray(
            data=transferred,
            dims=["country", "time"],
            coords=dict(
                country = discharge.country,
                time=discharge.time,
                ),
            ).to_dataset(name=f"{tech}_GWh")
        Scaled_total_transfer = scale_up(transferred,tech)
        
        print(f"Conversion for tech {tech} done. Now saving")
        # ===========================
        # === Step 3: Save output ===
        # ===========================
        for year in get_time_range(scenario):
            store_as_pandas_dataframe(
                Scaled_total_transfer[f"{tech}_GWh"], 
                f"hydro_{tech}_{year}",
                f"../output/bias_correction/{bc_realization}/{scenario}/{realization}/"
            )
        
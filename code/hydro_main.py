from bias_correction_methods import bias_correct_dataset
from utils import store_as_pandas_dataframe
from conversion_to_hydro import *
import sys
import xarray as xr
import pandas as pd
import numpy as np

# parameters
try: 
    year = sys.argv[1]
    realization = sys.argv[2]
    period = sys.argv[3]
except IndexError:
    year = "2010"
    realization = "1500"
    period = "HIST"

technologies = ["ror","inflow"]
rolling = {"ror":21,"inflow":3} # time to roll over - since inflow is weekly 3 weeks = 21 days

# =====================================================
# === Step 1: Open, bias correct and aggregate data ===
# =====================================================

# === CESM2 discharge === 
print("Open and bias correct CESM2 discharge")
discharge_full = open_discharge(year,realization=realization,period=period) # you can pass end_year to it to open several years in row
# Bias correction
discharge_full = bias_correct_dataset(discharge_full, "discharge").to_dataset(name="discharge")  
discharge_full = discharge_full.where(discharge_full.discharge > 0, other=0).convert_calendar("proleptic_gregorian") # to get numpy datetime (necessary for weekly resampling)
# aggregation
for tech in technologies:
    print(f"Aggregate CESM for tech {tech}")
    discharge = weighted_aggregation(discharge_full,tech)

    # === ERA5 discharge and ENTSO-e data (2017-2022) === 
    print(f"Open ERA5 discharge and ENTSO-e data for tech {tech}")
    # ENTSO-e
    calibration_ds = open_entsoe(tech) # conversion data set for inflows/ror
    [start_year,end_year] = calibration_ds.groupby("time.year").sum().year[[0,-1]].values
    # ERA5
    era_discharge = open_era().sel(time=slice(str(start_year),str(end_year)))
    if tech == "inflow":
        time_range = calibration_ds.time[[0,-1]].values # find values of start and end date, to open era5 weekly correctly
        era_discharge = open_weekly(era_discharge,time_range=time_range) # get era5 in weekly resolution
        discharge = open_weekly(discharge) # get cesm2 in weekly resolution
    #weighted aggregation, and making sure discharge and generation have same country list
    era_weighted = weighted_aggregation(era_discharge,tech)["discharge"].sel(country=calibration_ds.country)
    if tech =="ror":
        era_weighted["time"] = calibration_ds.time #ensuring same time stamp (discharge resamples to 11.30 every day and not 00.00)
    calibration_ds["discharge"] = era_weighted

    # rolling means
    discharge = discharge.rolling(time=rolling[tech],center=True).mean()
    calibration_ds = calibration_ds.rolling(time=rolling[tech],center=True).mean()
    # make sure that only countries present in calibration_ds are present in discharge
    discharge = discharge.sel(country=calibration_ds.country)

    print(f"All {tech} files opened and preprocessed. Conversion starting")

    # =====================================
    # === Step 2: Convert to hydropower ===
    # =====================================     
    transferred = []
    for country in discharge.country.values:
        [a1_opt, b2_opt, c2_opt],q =  get_pwlf(calibration_ds.sel(country=country).dropna(dim="time"),tech)
        transferred.append(piecewise_linear(
                                            discharge.sel(country=country).discharge.values, 
                                            a1_opt, 
                                            b2_opt, 
                                            c2_opt,
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
    store_as_pandas_dataframe(Scaled_total_transfer[f"{tech}_GWh"], f"hydro_{tech}_{year}")
    
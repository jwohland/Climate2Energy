import sys

from bias_correction_methods import bias_correct_xarray
from conversion_to_hydro import *
from utils import store_as_pandas_dataframe

if __name__ == "__main__":
    # parameters
    scenario = sys.argv[1]
    realization = sys.argv[2]
    bc_realization = sys.argv[3]
    input_path = sys.argv[4]
    input_info = sys.argv[5]
    try:
        output_path = sys.argv[6]
    except:
        output_path = get_output_path(bc_realization, scenario, realization)
    
    technologies = ["ror", "inflow"]
    rolling = {
        "ror": 21,
        "inflow": 3,
    }  # time to roll over - since inflow is weekly 3 weeks = 21 days

    # =====================================================
    # === Step 1: Open, bias correct and aggregate data ===
    # =====================================================

    # === CESM2 discharge ===
    print("Open CESM2 and ERA5 discharge")
    # open CESM2 discharge HIST, for bias correction
    discharge_full_for_bc = open_discharge_with_downscaling("historical", bc_realization)
    # opening ERA5 discharge for 1995-2015, for bias correction and for 2016-2023 for run-of-river calibration
    era5_discharge_full = open_era(discharge_full_for_bc.lat, discharge_full_for_bc.lon)
    # Bias correction
    try:
        bced_discharge = xr.open_dataset(f"{output_path}atmospheric_variables/bced_discharge_{input_info}.nc") 
    except:
        # open CESM2 discharge
        discharge_full = open_discharge(f"{input_path}")
        print("Bias correct CESM2")
        bced_discharge = (
            bias_correct_xarray(
                discharge_full.discharge,
                era5_discharge_full.sel(time=slice("1995", "2014")).discharge.load(), 
                discharge_full_for_bc.discharge,
            )
            .to_dataset(name="discharge")
            .convert_calendar("proleptic_gregorian")
        )  # to get numpy datetime (necessary for weekly resampling)
        # save bias corrected discharge
        bced_discharge.to_netcdf(
            f"{output_path}atmospheric_variables/bced_discharge_{input_info}.nc"
        )
    
    # aggregation
    for tech in technologies:
        print(f"Aggregate CESM2 and ERA5 for tech {tech}")
        discharge = weighted_aggregation(bced_discharge, tech).discharge
        if tech == "inflow":
            discharge = resample_weekly(discharge)  # get cesm2 in weekly resolution

        era5_discharge = weighted_aggregation(era5_discharge_full, tech)

        # === calibration data (ENTSO-e and ERA5 (2016-2023) ===
        print(f"Open ENTSO-e data for tech {tech}")
        calibration_ds = open_discharge_entsoe_for_calibration(era5_discharge, tech)
        # rolling means
        discharge = (
            discharge.rolling(time=rolling[tech], center=True, min_periods=1)
            .mean()
            .load()
        )
        calibration_ds = (
            calibration_ds.rolling(time=rolling[tech], center=True, min_periods=1)
            .mean()
            .load()
        )
        # make sure that only countries present in calibration_ds are present in discharge
        discharge = discharge.sel(country=calibration_ds.country)

        print(f"All {tech} files opened and preprocessed. Conversion starting")

        # =====================================
        # === Step 2: Convert to hydropower ===
        # =====================================
        transferred = []
        for country in discharge.country.values:
            [a1_opt, b1_opt, a2_opt, b2_opt], q = get_pwlf(
                calibration_ds.sel(country=country).dropna(dim="time"), tech
            )
            transferred.append(
                piecewise_linear(
                    discharge.sel(country=country).values,
                    a1_opt,
                    b1_opt,
                    a2_opt,
                    b2_opt,
                    q,
                )
            )
        transferred = xr.DataArray(
            data=transferred,
            dims=["country", "time"],
            coords=dict(
                country=discharge.country,
                time=discharge.time,
            ),
        ).to_dataset(name=f"{tech}_GWh")

        transferred = transferred.where(transferred > 0, 0)

        print(f"Conversion for tech {tech} done. Now saving")
        # ===========================
        # === Step 3: Save output ===
        # ===========================
        store_as_pandas_dataframe(
            transferred[f"{tech}_GWh"],
            f"hydro_{tech}_{input_info}",
            output_path,
        )

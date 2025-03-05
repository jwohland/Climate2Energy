import sys

from bias_correction_methods import bias_correct_xarray
from conversion_to_hydro import *
from utils import store_as_pandas_dataframe

if __name__ == "__main__":
    # parameters
    scenario = sys.argv[1]
    realization = sys.argv[2]
    bc_realization = sys.argv[3]

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
    # open CESM2 discharge
    discharge_full = open_discharge(scenario, realization)
    # open CESM2 discharge HIST, for bias correction
    discharge_full_for_bc = open_discharge("historical", bc_realization)
    # opening ERA5 discharge for 1995-2015, for bias correction and for 2016-2023 for run-of-river calibration
    era5_discharge_full = open_era(discharge_full.lat, discharge_full.lon)
    print("Bias correct CESM2")
    # Bias correction
    discharge_full = (
        bias_correct_xarray(
            discharge_full.discharge,
            era5_discharge_full.sel(time=slice("1995", "2014")).discharge.load(),
            discharge_full_for_bc.discharge,
        )
        .to_dataset(name="discharge")
        .convert_calendar("proleptic_gregorian")
    )  # to get numpy datetime (necessary for weekly resampling)
    # save bias corrected discharge, year for year
    for year in get_time_range(scenario):
        discharge_full.sel(time=str(year)).to_netcdf(
            f"{get_output_path(bc_realization, scenario, realization)}atmospheric_variables/bced_CESM2_discharge_{year}.nc"
        )
    # aggregation
    for tech in technologies:
        print(f"Aggregate CESM2 and ERA5 for tech {tech}")
        discharge = weighted_aggregation(discharge_full, tech).discharge
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
        for year in get_time_range(scenario):
            store_as_pandas_dataframe(
                transferred[f"{tech}_GWh"].sel(time=str(year)),
                f"hydro_{tech}_{year}",
                get_output_path(bc_realization, scenario, realization),
            )

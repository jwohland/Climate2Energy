from bias_correction_methods import *
from conversion_to_CF import *
from country_average import *
from utils import *
import sys
import time
import multiprocessing

####################
# Prep
####################


class Generation:
    def __init__(
        self,
        bc_realization,
        scenario,
        realization,
    ):
        self.bc_realization = bc_realization
        self.realization = realization
        self.scenario = scenario

    def conversion(self, year, test_data=False):
        """
        Compute wind and solar generation for a given
        - bias correction realization
        - scenario
        - realization
        - year

        If test_data==True, then only the first 10 time steps are computed.
        :param bc_realization: A, B, C
        :param scenario: historical, SSP245, SSP370
        :param realization: A,B,C
        :param year: 1995-2015 (historical), 2080-2099 SSPs
        :param test_data: True, False
        :return:
        """
        output_path = get_output_path(
            self.bc_realization, self.scenario, self.realization
        )
        print(f"Open files for year {year}")
        ts = time.time()
        ####################
        # Step 0: Open data
        ####################
        ds_wind, ds_rho, ds_PV = open_wind_solar(
            year, self.scenario, self.realization, test_data=test_data
        )  # test_data=True allows for quick test with only 10 timesteps
        print(
            f"Files opened. Took {int((time.time()-ts)/60)} minutes. Next: bias correction"
        )
        ts = time.time()
        ds_wind.load()
        ds_PV.load()
        ds_rho.load()
        print(
            f"Files loaded. Took {int((time.time()-ts)/60)} minutes. Next: bias correction"
        )
        ####################
        # Step 1: Bias correction
        ####################
        ts = time.time()
        ds_corr_PV = xr.Dataset()
        for var in ["temperature", "global_horizontal"]:
            print(var)
            ds_corr_PV[var] = bias_correct_dataset(ds_PV, var, bc_realization)

        print("s_hub")
        # Extrapolate model to 100m (i.e., ERA5 height), then bias correct
        ds_interpolated, alpha = interpolate_wind_xr(
            ds_wind, 100
        )  # careful: this outputs s_hub even though these are 100m winds
        ds_corr_wind = bias_correct_dataset(ds_interpolated, "s_hub", bc_realization)
        print(
            f"Bias correction finished. Took {int((time.time()-ts)/60)} minutes. Next: conversion to capacity factors"
        )

        # Save bias-corrected fields
        bc_output_path = f"{output_path}atmospheric_variables/"
        ds_corr_wind.to_netcdf(f"{bc_output_path}bced_CESM2_s100_{year}.nc")
        ds_corr_PV["temperature"].to_dataset().to_netcdf(
            f"{bc_output_path}bced_CESM2_temperature_{year}.nc"
        )
        ds_corr_PV["global_horizontal"].to_dataset().to_netcdf(
            f"{bc_output_path}bced_CESM2_global-horizontal_{year}.nc"
        )

        ####################
        # Step 2: Calculate capacity factors
        ####################
        ds_CF_PV = calculate_PV(ds_corr_PV, params=None)
        ts = time.time()
        ds_CF_wind_corrected = convert_winds(
            ds_corr_wind,
            ds_rho,
            alpha,
        )  # this expects that ds has variable called s_hub with hub height winds
        print(
            f"Wind CF with density correction  finished. Took {int((time.time()-ts)/60)} minutes."
        )
        ts = time.time()
        ds_CF_wind_uncorrected = convert_winds(
            ds_corr_wind,
            ds_rho,
            alpha,
            density_correct=False,  # if set to False, no density correction is performed
        )  # this expects that ds has variable called s_hub with hub height winds
        print(
            f"Wind CF without density correction  finished. Took {int((time.time() - ts) / 60)} minutes."
        )

        # Save capacity factor fields
        ds_CF_PV.to_netcdf(f"{output_path}output_variables/PV_{year}.nc")
        ds_CF_wind_corrected.to_netcdf(
            f"{output_path}output_variables/Wind-power_{str(year)}_density-corrected.nc"
        )
        ds_CF_wind_uncorrected.to_netcdf(
            f"{output_path}output_variables/Wind-power_{str(year)}.nc"
        )
        print("Capacity factors computed. Next: country subsets and saving data")

        # Step 3: subset countries
        ts = time.time()
        ds_CF_PV_countries = country_means(ds_CF_PV)
        ds_CF_wind_countries = country_means(ds_CF_wind_corrected)
        ds_CF_wind_countries_offshore = country_means(
            ds_CF_wind_corrected, onshore=False
        )
        ds_CF_wind_countries_uncorrected = country_means(ds_CF_wind_uncorrected)
        ds_CF_wind_countries_offshore_uncorrected = country_means(
            ds_CF_wind_uncorrected, onshore=False
        )
        print(
            f"Country subsetting finished. Took {int((time.time() - ts) / 60)} minutes. "
        )

        # Step4: Save capacity factor csv files
        # wind
        for method in ["corrected", "uncorrected"]:
            for onshore in [True, False]:
                if onshore:
                    if method == "corrected":
                        ds_tmp_full = ds_CF_wind_countries
                    else:
                        ds_tmp_full = ds_CF_wind_countries_uncorrected
                else:
                    if method == "corrected":
                        ds_tmp_full = ds_CF_wind_countries_offshore
                    else:
                        ds_tmp_full = ds_CF_wind_countries_offshore_uncorrected
                for i in range(3):
                    ds_tmp = ds_tmp_full.isel(turbine=i)
                    turbine_name = str(ds_tmp.turbine.values)
                    store_as_pandas_dataframe(
                        ds_tmp["CF_wind"],
                        name=f"Wind-power_{year}_{turbine_name}_onshore_{onshore}_density_{method}",
                        path=output_path,
                    )
        # PV
        store_as_pandas_dataframe(
            ds_CF_PV_countries["pv"], name=f"PV_{year}", path=output_path
        )
        print("Everything finished and saved")


if __name__ == "__main__":
    # Create directory structure
    create_directories()

    scenario = str(sys.argv[1])
    realization = str(sys.argv[2])
    bc_realization = str(sys.argv[3])
    print(
        f"Computing generation for scenario {scenario} realization {realization},"
        f" using bias-correction based on historical realization {bc_realization}"
    )
    generation = Generation(bc_realization, scenario, realization)
    # execute with one process per year
    with multiprocessing.Pool(20) as pool:
        pool.map(generation.conversion, get_time_range(scenario))

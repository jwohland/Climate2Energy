from bias_correction_methods import *
from utils import *
import sys
import time
import multiprocessing

class Correction:
    def __init__(
        self,
        bc_realization,
        scenario,
        realization,
    ):
        self.bc_realization = bc_realization
        self.realization = realization
        self.scenario = scenario
    def bias_correction(self, year, test_data=False):
        """
        Compute bias correction for a given
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
        bc_output_path = f"{output_path}atmospheric_variables/"
        # Check if output exists already
        try:
            ds_corr_wind = xr.open_dataset(f"{bc_output_path}bced_CESM2_s100_{year}.nc")
        except FileNotFoundError:
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

            ####################
            # Step 1: Bias correction
            ####################
            ts = time.time()
            ds_corr_PV = xr.Dataset()
            for var in ["temperature", "global_horizontal"]:
                print(var)
                ds_corr_PV[var] = bias_correct_dataset(ds_PV, var, self.bc_realization)

            print("s_hub")
            # Extrapolate model to 100m (i.e., ERA5 height), then bias correct
            ds_interpolated, da_alpha = interpolate_wind_xr(
                ds_wind, 100
            )  # careful: this outputs s_hub even though these are 100m winds
            ds_corr_wind = bias_correct_dataset(ds_interpolated, "s_hub", self.bc_realization)
            print(
                f"Bias correction finished. Took {int((time.time()-ts)/60)} minutes."
            )

            # Save bias-corrected fields
            ds_corr_wind.to_netcdf(f"{bc_output_path}bced_CESM2_s100_{year}.nc")
            ds_corr_PV["temperature"].to_dataset().to_netcdf(
                f"{bc_output_path}bced_CESM2_temperature_{year}.nc"
            )
            ds_corr_PV["global_horizontal"].to_dataset().to_netcdf(
                f"{bc_output_path}bced_CESM2_global-horizontal_{year}.nc"
            )
            # Save other needed files
            da_alpha.to_dataset(name="alpha").to_netcdf(f"{bc_output_path}CESM2_alpha_{year}.nc")
            ds_rho.to_netcdf(f"{bc_output_path}CESM2_rho_{year}.nc")


if __name__ == "__main__":
    scenario = str(sys.argv[1])
    realization = str(sys.argv[2])
    bc_realization = str(sys.argv[3])
    print(
        f"Computing generation for scenario {scenario} realization {realization},"
        f" using bias-correction based on historical realization {bc_realization}"
    )
    correction = Correction(bc_realization, scenario, realization)
    # execute with one process per year
    with multiprocessing.Pool(20) as pool:
        pool.map(correction.bias_correction, get_time_range(scenario))
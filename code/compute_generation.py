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
        density_correct=True,
        output_path=False
    ):
        self.bc_realization = bc_realization
        self.realization = realization
        self.scenario = scenario
        self.density_correct = density_correct
        # add your own output path if needed
        if output_path == False or type(output_path) != str:
            self.output_path = get_output_path(bc_realization, scenario, realization)
        else:
            self.output_path = output_path
        self.bc_output_path = f"{self.output_path}atmospheric_variables/"

    def conversion_wind(self, input_info):
        """
        Compute wind generation for a given
        - bias correction realization
        - scenario
        - realization
        - input_info

        If test_data==True, then only the first 10 time steps are computed.
        :param bc_realization: A, B, C
        :param scenario: historical, SSP245, SSP370
        :param realization: A,B,C
        :param input_info: description of what you're inputting, what you want each output file to be named
        :param test_data: True, False
        :return:
        """
        ####################
        # Step 1: Open bias corrected data
        ####################
        ds_corr_wind = xr.open_dataset(
            f"{self.bc_output_path}bced_s100_{input_info}.nc"
        )
        alpha = xr.open_dataset(f"{self.bc_output_path}alpha_{input_info}.nc")
        if self.density_correct == True:
            ds_rho = xr.open_dataset(f"{self.bc_output_path}rho_{input_info}.nc")
        else:
            ds_rho = None

        ####################
        # Step 2: Calculate capacity factors
        ####################
        ts = time.time()
        ds_CF_wind = convert_winds(
            ds_corr_wind,
            alpha,
            density_correct=ds_rho,
        )  # this expects that ds has variable called s_hub with hub height winds
        print(f"Wind CF finished. Took {int((time.time()-ts)/60)} minutes.")

        # Save capacity factor fields
        filename = f"Wind-power_{input_info}"
        if self.density_correct:
            filename += "_density-corrected"
        ds_CF_wind.to_netcdf(f"{self.output_path}output_variables/{filename}.nc")
        print("Capacity factors computed. Next: country subsets and saving data")

        # Step 3: subset countries
        ts = time.time()
        ds_CF_wind_countries = country_means(ds_CF_wind)
        ds_CF_wind_countries_offshore = country_means(ds_CF_wind, onshore=False)
        print(
            f"Country subsetting finished. Took {int((time.time() - ts) / 60)} minutes. "
        )

        # Step4: Save capacity factor csv files
        # wind
        for onshore in [True, False]:
            if onshore:
                ds_tmp_full = ds_CF_wind_countries
            else:
                ds_tmp_full = ds_CF_wind_countries_offshore
            for i in range(3):
                ds_tmp = ds_tmp_full.isel(turbine=i)
                turbine_name = str(ds_tmp.turbine.values)
                filename = f"Wind-power_{input_info}_{turbine_name}_onshore_{onshore}"
                if self.density_correct:
                    filename += "_density_corrected"
                store_as_pandas_dataframe(
                    ds_tmp["CF_wind"],
                    name=filename,
                    path=self.output_path,
                )
        print("Everything finished and saved")

    def conversion_PV(self, input_info,freq):
        """
        Compute solar PV generation for a given
        - bias correction realization
        - scenario
        - realization
        - input_info

        If test_data==True, then only the first 10 time steps are computed.
        :param bc_realization: A, B, C
        :param scenario: historical, SSP245, SSP370
        :param realization: A,B,C
        :param input_info: description of what you're inputting, what you want each output file to be named
        :param test_data: True, False
        :return:
        """
        print(f"Open files for {input_info}")
        ####################
        # Step 1: Open bias corrected data
        ####################
        ds_corr_PV = xr.merge(
            [
                xr.open_dataset(
                    f"{self.bc_output_path}bced_temperature_{input_info}.nc"
                ),
                xr.open_dataset(
                    f"{self.bc_output_path}bced_global-horizontal_{input_info}.nc"
                ),
            ]
        )

        ####################
        # Step 2: Calculate capacity factors
        ####################
        ds_CF_PV = calculate_PV(ds_corr_PV, params=None, num_cores=32,freq=freq)

        # Save capacity factor fields
        ds_CF_PV.to_netcdf(f"{self.output_path}output_variables/PV_{input_info}.nc")
        print("Capacity factors computed. Next: country subsets and saving data")

        # Step 3: subset countries
        ds_CF_PV_countries = country_means(ds_CF_PV)
        print(f"Country subsetting finished.")

        # Step4: Save capacity factor csv files
        store_as_pandas_dataframe(
            ds_CF_PV_countries["pv"], name=f"PV_{input_info}", path=self.output_path
        )
        print("Everything finished and saved")


if __name__ == "__main__":
    scenario = str(sys.argv[1])
    realization = str(sys.argv[2])
    bc_realization = str(sys.argv[3])
    technology = str(sys.argv[4])
    input_info = str(sys.argv[5])
    try:
        density_correct = eval(sys.argv[6])
    except:
        density_correct = True
        print("Defaults to with density correction.")
    try:
        output_path = sys.argv[7]
    except:
        output_path = False # defaults to output path used in CESM2energy
    try:
        freq = sys.argv[8]
    except:
        freq = "H"
    print(
        f"Computing generation for scenario {scenario}, realization {realization},"
        f" using bias-correction based on historical realization {bc_realization}"
        f" and with density correction set to {density_correct}."
    )
    generation = Generation(
        bc_realization, scenario, realization, density_correct=density_correct,output_path=output_path
    )
    if technology == "Wind":
        generation.conversion_wind(input_info)
    elif technology == "PV":
        generation.conversion_PV(input_info,freq)
    else:
        print("Technology not valid")

from country_average import *
from utils import *
import pandas as pd
import demand_ninja  # todo currently is done in seperate environment. Can we integrate it?
import subprocess


def convert_xarray_demandninja(ilat, ilon):  # todo when to choose location and country?
    """
    Takes climate model inputs (as xarray datasets) and
    reformats them as pandas timeseries
    :param ds:
    :return:
    """

    # todo the following just creates placeholder data of the right format. This needs to be replaced with actual
    # todo data once Urs' simulations are completed
    year = "2015"
    ds_wind, ds_PV = open_wind_solar(
        year, test_data=True
    )  # test_data=True allows for quick test with only 10 timesteps
    ds_wind = ds_wind.isel(lat=ilat, lon=ilon, drop=True)
    ds_PV = ds_PV.isel(lat=ilat, lon=ilon, drop=True)
    df = ds_PV[["global_horizontal", "temperature"]].to_dataframe()
    df["temperature"] -= 273.15  # convert from K to C
    ds_wind = (
        ds_wind["S"].isel(lev=0, drop=True).squeeze() * 0.2
    )  # brutal correction to get 2m winds
    ds_wind["time"] = ds_PV["time"]  # time index that GSEE understands
    df["wind_speed_2m"] = ds_wind.to_dataframe()
    df["humidity"] = df["wind_speed_2m"] * 0 + np.random.random(
        df["wind_speed_2m"].size
    )  # adding humidity as random numbers between 0 and 1
    df = df.rename(columns={"global_horizontal": "radiation_global_horizontal"})
    # Need hourly
    df = df.resample("H").interpolate()
    # check that output is hourly
    return df


def reformat_demandninja(df):
    """
    Reformat results to have this structure:
        type      | country | timestep1   | timestep2 | ...   | timestep N
        heating   | Austria | value1      | value 2   | ...   | value N
    :param df:
    :return:
    """
    df = (
        df[
            ["heating_demand", "cooling_demand", "country"]
        ]  # only variables of interest
        .pivot(columns="country")  # group by countries
        .transpose()  # make format align with CF output
    )
    return df


def compute_country_population_density():
    """
    Compute Dataset with population information on the CESM2
    climate model grid per country. Output is the share of a country
    that lives within the boarders of a specific CESM2 grid cell.

    Based on UN WPP-Adjusted Population Density, v4.11
    :return:
    """
    ds_pop = xr.open_dataset(
        "../inputs/gpw_v4_population_density_adjusted_rev11_2pt5_min.nc"
    )
    ds_pop = ds_pop.sel(
        longitude=slice(-15, 50), latitude=slice(75, 30)
    )  # select Europe todo should I fix the decreasing latitude here?
    var_name = "UN WPP-Adjusted Population Density, v4.11 (2000, 2005, 2010, 2015, 2020): 2.5 arc-minutes"
    ds_pop = ds_pop.isel(
        raster=3, drop=True
    )  # that is 2015 population data in line with the year used by Staffell et al (2023)
    ds_pop_countries = cut_out_countries(ds_pop)
    # normalize to 1 such that values mean percentage of country population per grid cell
    ds_list = []
    for country in ds_pop_countries.country.values:
        ds_tmp = remap_to_CESM2(
            ds_pop_countries.sel(country=country)
        )  # todo why does this not work for all countries at once?
        ds_tmp[var_name] /= ds_tmp[var_name].sum()
        ds_tmp["country"] = country
        ds_list.append(ds_tmp)
    return xr.concat(ds_list, dim="country")


def remap_to_CESM2(ds):
    """
    Takes population data at high resolution (2.5 minutes) and remapps it conservatively to CESM2 resolution.
    :param ds:
    :return:
    """
    ds.to_netcdf("../output/pop_tmp.nc")
    subprocess.run(
        "cdo remapcon,../inputs/CESM_atm_grid.txt ../output/pop_tmp.nc ../output/pop_remapped.nc",
        shell=True,
    )  # use cdo to remap todo  Warning (find_time_vars): Time variable >raster< not found!
    ds = xr.open_dataset("../output/pop_remapped.nc")
    ds = select_Europe(zero_mean_longitudes(ds))
    return ds


demand_params = pd.read_csv(
    "../inputs/demand_ninja_parameters.csv", index_col=0, skiprows=2
)
pop_density = compute_country_population_density()
var_name = "UN WPP-Adjusted Population Density, v4.11 (2000, 2005, 2010, 2015, 2020): 2.5 arc-minutes"
year = 2015  # todo turn this into function parameter

result_list = []  # to store country level results
for country in demand_params.index:
    params = demand_params.loc[
        country
    ]  # country specific heating and cooling parameters
    tmp_pop = pop_density.sel(country)
    # computed weighted demand per country
    weight_list, demand_list = [], []
    for ilat in range(48):
        print(ilat)
        for ilon in range(53):
            local_population = tmp_pop.isel(lat=ilat, lon=ilon)[var_name].values
            if np.isfinite(local_population):
                df = convert_xarray_demandninja(ilat, ilon)
                print("opened")
                # can not currently execute demand ninja in this environment
                demand_list.append(demand_ninja.demand(df.copy) * local_population)

        # todo: need loop over all locations in a country here
        result = demand_ninja.demand(df.copy(), raw=False, **params)
    result["country"] = country
    result_list.append(result)
results = pd.concat(result_list)

results = reformat_demandninja(results)

# Save # todo should this be moved to run_all?
for demand_type in ["heating_demand", "cooling_demand"]:
    results.loc[demand_type].to_csv(
        "../output/" + demand_type + "_" + str(year) + ".csv"
    )

# Output: dataframe with

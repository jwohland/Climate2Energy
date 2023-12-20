from country_average import *
from utils import *
import pandas as pd
import demand_ninja  # todo currently is done in seperate environment. Can we integrate it?
import subprocess


def open_xarray_demandninja(year=1990):
    """
    open full datasets with variables needed for demand calculation
    """
    path = "/net/meso/climphys/cesm212/b.e212.BHISTcmip6.f09_g17.1500/archive/"
    ds_atm = xr.open_dataset(
        path
        + "atm/hist/b.e212.BHISTcmip6.f09_g17.1500.cam.h6."
        + str(year)
        + "-01-01-03600.nc",
        chunks={"lat": 10, "lon": 10, "time": 3000},
    )
    ds_atm = select_Europe(
        zero_mean_longitudes(ds_atm[["FSDS", "TREFHT", "U10", "QREFHT"]])
    )
    # Correct units so that they match with demandninja
    ds_atm["QREFHT"] *= 1000  # CESM2 gives kg/kg but demandninja wants g/kg
    ds_atm["U10"] *= (2 / 10) ** 0.14  # power law conversion from 10m to 2m
    ds_atm["TREFHT"] -= 273.15  # convert from K to C
    return ds_atm


def pick_convert_demandninja(ds, ilat, ilon):
    """
    Pick desired location and convert dataset into pandas dataframe at this location
    """
    ds_tmp = ds.isel(lat=ilat, lon=ilon, drop=True)
    df = ds_tmp.to_dataframe()
    df = df.rename(
        columns={
            "FSDS": "radiation_global_horizontal",
            "TREFHT": "temperature",
            "U10": "wind_speed_2m",
            "QREFHT": "humidity",
        }
    )
    df.index = df.index.to_datetimeindex(
        unsafe=True
    )  # ninja needs time in datetimeindex format, unsafe is ok because non-leap year have been manually checked
    # check that values are plausible
    sense_check_demandninja_inputs(df)
    return df


def sense_check_demandninja_inputs(df):
    """
    Some plausibility checks on the inputs for the demand calculation
    :param df:
    :return:
    """
    assert (df.radiation_global_horizontal >= 0).all()  # radiation must be positive
    assert (np.absolute(df.temperature) <= 100).all()  # temps must be within -100 to 100 °C
    assert (df.wind_speed_2m >= 0).all()  # wind must be positive
    assert (df.wind_speed_2m <= 100).all()  # winds cannot be unrealistically high (100 m/s)
    assert (df.humidity >= 0).all()  # humidity cannot be negative


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
    )  # select Europe. I do not use the function because latitude sorting inverted here.
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
        )  # does not work for all countries at once. This loop is acceptable in terms of performance.
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
        "cdo -s remapcon,../inputs/CESM_atm_grid.txt ../output/pop_tmp.nc ../output/pop_remapped.nc",
        shell=True,
    )  # use cdo to remap where -s avoids output  weights and domain size output and -w avoids a "Time variable >raster< not found!" warning. (data has no time dimension)
    # todo  Warning (find_time_vars): Time variable >raster< not found!
    ds = xr.open_dataset("../output/pop_remapped.nc")
    ds = select_Europe(zero_mean_longitudes(ds))
    return ds


def parameter_fill_ninja(df):
    """
    Some countries that we model do not have paramerts in the demand-ninja inputs.

    Sometimes this is related to the use of different names (Czechia vs. Czech Republic),
    different spatial aggregation (United Kingdom vs. Great Britain) or because some small countries are
    not included ('Albania', 'Bosnia and Herzegovina', 'Croatia', 'Montenegro', 'Macedonia',
    'Serbia', 'Slovenia', 'Latvia').

    These parameter holes are filled here. Justification is given in issue #19 on github.
    :param country_name:
    :return:
    """
    df.rename(
        index={"Great Britain": "United Kingdom"}, inplace=True
    )  # slightly different area
    df.loc["United Kingdom"]["heating_power"] *= 1.025
    df.loc["United Kingdom"]["cooling_power"] *= 1.025
    df.rename(index={"Czechia": "Czech Republic"}, inplace=True)  # naming mismatch
    # relatively small countries in SE Europe: replace by mean of neighbors
    # and scale heating / cooling power by population
    neighbors = ["Italy", "Austria", "Hungary", "Romania", "Bulgaria", "Greece"]
    mean_neighbors = df.loc[neighbors].mean()
    pop_total = pd.read_csv("../inputs/World_bank_population.csv", skiprows=3)[
        ["Country Name", "2020"]
    ].set_index(
        "Country Name"
    )  # world bank total population data downloaded from https://data.worldbank.org/indicator/SP.POP.TOTL
    N_ref = int(pop_total.loc[neighbors].mean())
    for country in [
        "Albania",
        "Bosnia and Herzegovina",
        "Croatia",
        "Montenegro",
        "Macedonia",
        "Serbia",
        "Slovenia",
    ]:
        df.loc[country] = mean_neighbors
        if country == "Macedonia":
            N = int(
                pop_total.loc["North Macedonia"]
            )  # world bank uses "North Macedonia" instead of "Macedonia" which is the correct term today
        else:
            N = int(pop_total.loc[country])
        df.loc[country]["heating_power"] *= N / N_ref
        df.loc[country]["cooling_power"] *= N / N_ref
    return df


demand_params = pd.read_csv(
    "../inputs/demand_ninja_parameters.csv", index_col=0, skiprows=2
)
demand_params = parameter_fill_ninja(demand_params)  # fill missing values
pop_density = compute_country_population_density()
var_name = "UN WPP-Adjusted Population Density, v4.11 (2000, 2005, 2010, 2015, 2020): 2.5 arc-minutes"

year = 1990  # todo turn this into function parameter
ds_ninja = open_xarray_demandninja(year)
ds_ninja.load()  # loading here once speeds up the following loop

result_list = []  # to store country level results
for country in demand_params.index:
    print(country)
    params = demand_params.loc[
        country
    ]  # country specific heating and cooling parameters
    tmp_pop = pop_density.sel(country=country)
    # computed weighted demand per country
    demand_list = []
    for ilat in range(ds_ninja.lat.size):
        for ilon in range(ds_ninja.lon.size):
            local_population = tmp_pop.isel(lat=ilat, lon=ilon)[var_name].values
            if np.isfinite(local_population):
                df = pick_convert_demandninja(ds_ninja, ilat, ilon)
                demand_list.append(demand_ninja.demand(df.copy(), **params) * local_population)
    df_demand = pd.concat(demand_list)  # combine all locations
    result = df_demand.groupby(df_demand.index).sum()  # country sum
    result["country"] = country
    result_list.append(result)
results = pd.concat(result_list)

# todo add scaling to  meet JRC observed heating demand under the assumption that all heating is electrified
results = reformat_demandninja(results)

# Save # todo should this be moved to run_all?
for demand_type in ["heating_demand", "cooling_demand"]:
    results.loc[demand_type].to_csv(
        "../output/" + demand_type + "_" + str(year) + ".csv"
    )

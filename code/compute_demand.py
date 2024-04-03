from country_average import *
from utils import *
import pandas as pd
import demand_ninja  # todo currently is done in seperate environment. Can we integrate it?
import subprocess
import sys


def open_xarray_demandninja(year, bc_realization, scenario, realization):
    """
    Open full datasets with variables needed for demand calculation

    Primary variables (i.e., temperature and radiation) are loaded as pre-computed
    bias-corrected fields.

    Secondary variables (i.e., humidity and 10m winds) are loaded as raw CESM2 output.
    """
    # Open primary variables that have been bias-corrected already
    output_path = get_output_path(bc_realization, scenario, realization)
    try:
        ds_temp = xr.open_dataset(
            f"{output_path}atmospheric_variables/bced_CESM2_temperature_{year}.nc"
        )
        ds_radiation = xr.open_dataset(
            f"{output_path}atmospheric_variables/bced_CESM2_global-horizontal_{year}.nc"
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"Bias-corrected temperature and radiation input files do not exist {bc_realization} {scenario} {realization}"
        )

    ds_atm = xr.open_dataset(
        get_input_filename(scenario, realization, year),
        chunks={"lat": 10, "lon": 10, "time": 3000},
    )
    ds_atm = select_Europe(zero_mean_longitudes(ds_atm[["U10", "QREFHT"]]))
    # Correct units so that they match with demandninja
    ds_atm["QREFHT"] *= 1000  # CESM2 gives kg/kg but demandninja wants g/kg
    ds_atm["U10"] *= (2 / 10) ** 0.14  # power law conversion from 10m to 2m
    ds_atm["FSDS"] = ds_radiation
    ds_atm[
        "TREFHT"
    ] = ds_temp  # todo check that this one is already in C and does not need conversion
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
    assert (
        np.absolute(df.temperature) <= 100
    ).all()  # temps must be within -100 to 100 °C
    assert (df.wind_speed_2m >= 0).all()  # wind must be positive
    assert (
        df.wind_speed_2m <= 100
    ).all()  # winds cannot be unrealistically high (100 m/s)
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
    Takes population data at high resolution (2.5 minutes) and remaps it conservatively to CESM2 resolution.
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


def country_mapping_JRC_CESM2Energy():
    """
    Country names are different in JRC and CESM2Energy. This dictionary does the translation.

    No data means that the country exists in CESM2Energy but not in the JRC database.
    :return:
    """
    country_mapping = {
        "Albania": "no_data",
        "Austria": "AT",
        "Belgium": "BE",
        "Bosnia and Herzegovina": "no_data",
        "Bulgaria": "BG",
        "Croatia": "HR",
        "Czech Republic": "CZ",
        "Denmark": "DK",
        "Estonia": "EE",
        "Finland": "FI",
        "France": "FR",
        "Germany": "DE",
        "Greece": "EL",
        "Hungary": "HU",
        "Ireland": "IE",
        "Italy": "IT",
        "Latvia": "LV",
        "Lithuania": "LT",
        "Macedonia": "no_data",
        "Montenegro": "no_data",
        "Netherlands": "NL",
        "Norway": "no_data",
        "Poland": "PL",
        "Portugal": "PT",
        "Romania": "RO",
        "Serbia": "no_data",
        "Slovakia": "SK",
        "Slovenia": "SI",
        "Spain": "ES",
        "Sweden": "SE",
        "Switzerland": "no_data",
        "United Kingdom": "UK",
    }
    return country_mapping


def compute_electrified_share(country, metric="fec"):
    """
    Compute the electrified share of heating demand according to the JRC database.

    Shares have values between 0 and 1, i.e., no to full electrification of heating.
    Values are computed for the Residential and Tertiary sector. Final energy consumption
    is evaluated per default.
    """
    if country != "no_data":
        df = pd.read_excel(
            "../inputs/JRC/JRC-IDEES-2015_Residential_" + country + ".xlsx",
            sheet_name="RES_hh_" + metric,
            index_col=0,
        )
        demand_res_ktoe = (
            df.loc["Advanced electric heating"][2015]
            + df.loc["Conventional electric heating"][2015]
        )
        demand_res_total_ktoe = df.loc["Space heating"][2015]
        df = pd.read_excel(
            "../inputs/JRC/JRC-IDEES-2015_Tertiary_" + country + ".xlsx",
            sheet_name="SER_hh_" + metric,
            index_col=0,
        )
        demand_ser_ktoe = (
            df.loc["Advanced electric heating"][2015]
            + df.loc["Conventional electric heating"][2015]
        )
        demand_ser_total_ktoe = df.loc["Space heating"][2015]

        electrified_share = (demand_res_ktoe + demand_ser_ktoe) / (
            demand_res_total_ktoe + demand_ser_total_ktoe
        )

        return electrified_share


def compute_share_df():
    """
    Loop over the countries and compute the electrified heating share.

    For 7 countries that are included in CESM2Energy, there is no entry in JRC.
    We fill those with the data from similar countries, see below for the exact mapping.
    :return:
    """
    country_mapping = country_mapping_JRC_CESM2Energy()
    share_dict = {
        country: compute_electrified_share(country_mapping[country])
        for country in country_mapping.keys()
    }
    df = pd.Series(share_dict, name="electrified_heating_share").to_frame()
    # Make assumptions to fill the holes
    df.loc["Albania"] = df.loc["Romania"]
    df.loc["Bosnia and Herzegovina"] = df.loc["Slovakia"]
    df.loc["Macedonia"] = df.loc["Slovenia"]
    df.loc["Montenegro"] = df.loc["Slovakia"]
    df.loc["Serbia"] = df.loc["Bulgaria"]
    df.loc["Norway"] = df.loc["Sweden"]
    df.loc["Switzerland"] = df.loc["Austria"]
    return df


def scale_heating_demand(target_share, df_current_share, df_demand):
    """
    Scale heating demand from its current share to a target share.

    Shares is given in the range from 0 to 1 where 0 means that no heating is
    supplied via electricity and 1 means that all of it is electrified.
    """
    for country in df_demand.index:
        df_demand.loc[country] *= (
            target_share / df_current_share.loc[country]["electrified_heating_share"]
        )
    return df_demand


def demand_conversion(bc_realization, scenario, realization):
    """
    Execute conversion from CESM2 output to heating and cooling demand over all historical years (1990 - 2010).

    This outputs two version of heating demand.

    The first, ending in "_fully_electrified.csv", assumes that heating demand is fully met with electricity
    using the current mix of electrical heating technologies in every country.

    The other output is not scaled and represents the demandninja raw output when driven with CESM2.

    :return:
    """
    demand_params = pd.read_csv(
        "../inputs/demand_ninja_parameters.csv", index_col=0, skiprows=2
    )
    demand_params = parameter_fill_ninja(demand_params)  # fill missing values
    pop_density = compute_country_population_density()
    var_name = "UN WPP-Adjusted Population Density, v4.11 (2000, 2005, 2010, 2015, 2020): 2.5 arc-minutes"
    output_path = get_output_path(bc_realization, scenario, realization)
    for year in get_time_range(scenario):
        ds_ninja = open_xarray_demandninja(year, bc_realization, scenario, realization)
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
                        demand_list.append(
                            demand_ninja.demand(df.copy(), **params) * local_population
                        )
            df_demand = pd.concat(demand_list)  # combine all locations
            result = df_demand.groupby(df_demand.index).sum()  # country sum
            result["country"] = country
            result_list.append(result)
        results = reformat_demandninja(pd.concat(result_list))

        # Save raw
        for demand_type in ["heating_demand", "cooling_demand"]:
            file_suffix = demand_type.replace("_", "-") + "_" + str(year)
            results.loc[demand_type].to_csv(f"{output_path}{file_suffix}.csv")
            if demand_type == "heating_demand":
                # Save scaled heating
                file_suffix += "_fully-electrified"
                # scale to target share
                df_heating_scaled = scale_heating_demand(
                    1, compute_share_df(), results.loc[demand_type].copy()
                )
                df_heating_scaled.to_csv(f"{output_path}{file_suffix}.csv")


if __name__ == "__main__":
    scenario = str(sys.argv[1])
    realization = str(sys.argv[2])
    bc_realization = str(sys.argv[3])
    demand_conversion(bc_realization, scenario, realization)

import datetime as dt
import glob
import os

import cftime
import numpy as np
import pandas as pd
import xarray as xr
from scipy.optimize import minimize
from tqdm import tqdm

from utils import (
    zero_mean_longitudes,
    select_Europe,
    get_time_range,
    CESM2_REALIZATION_DICT,
    get_output_path,
)


# =================================
# === PREPROCESSING AND OPENING ===
# =================================


def downscale(ds_discharge, ds_runoff, file_name):
    """
    Takes monthly mean river discharge and interpolates to daily data assuming
    that the sub-monthly evolution of river discharge and runoff are identical.

    :param ds_discharge: Monthly river discharge
    :param ds_runoff: Daily runoff
    :param file_name: Output file name including the path to the file
    :return:
    """
    ## Do mean of runoff over latitude and longitude (One value per day, spatially aggregated)
    ds_runoff_mean = ds_runoff.mean(dim=["lon", "lat"])
    ## Get the monthly mean of runoff, and then the normalize profiles of runoff
    ds_runoff_mean.coords["year_month"] = (
        "time",
        ds_runoff_mean.time.dt.strftime("%Y-%m").data,
    )

    monthly_mean = ds_runoff_mean.groupby("year_month").mean(dim="time")
    year_month = ds_runoff_mean.time.dt.strftime("%Y-%m").data
    monthly_mean_data = monthly_mean.sel(year_month=year_month).runoff.data
    runoff_monthly_mean = xr.DataArray(
        data=monthly_mean_data, dims="time", coords={"time": ds_runoff_mean.time}
    )
    ds_runoff_mean["runoff_normalized"] = ds_runoff_mean.runoff / runoff_monthly_mean
    ds_runoff_mean = ds_runoff_mean.drop_vars("year_month")

    ## Sincronyze all time stamps to midnight
    def normalize_to_midnight(time_array):
        return [
            cftime.DatetimeNoLeap(
                t.year, t.month, t.day, 0, 0, 0, 0, has_year_zero=t.has_year_zero
            )
            for t in time_array
        ]

    ds_runoff_mean["time"] = normalize_to_midnight(ds_runoff_mean.time.values)
    ## Expand monthly discharge to daily discharge
    ds_discharge_daily = (
        ds_discharge.resample(time="1D")
        .ffill()
        .rename({"discharge": "discharge_expanded"})
    )
    ds_discharge_daily["time"] = ds_discharge_daily.time + dt.timedelta(
        days=-31
    )  # shift one month back
    ## Match time coordinates of the two datasets: discharge_daily and runoff_mean
    ds_runoff_mean = ds_runoff_mean.sel(time=ds_discharge_daily.time)
    ## Expand runoff_mean, to include latitude and longitude
    ds_runoff_mean = ds_runoff_mean.broadcast_like(ds_discharge_daily)
    ## Calculate daily values of river discharge
    ds_discharge_daily["discharge"] = (
        ds_discharge_daily.discharge_expanded * ds_runoff_mean.runoff_normalized
    )
    ds_discharge_daily.to_netcdf(file_name)


def preprocess_hydro_cesm(ds, var="discharge"):
    """
    Returns a dataset of river discharge or runoff (param var) for Europe
    :param ds:
    :param var: str
    """
    ds = select_Europe(
        zero_mean_longitudes(ds)
    )  # selecting area and settin long to -180,180
    if var == "discharge":
        land_dis = xr.where(
            ds.RIVER_DISCHARGE_OVER_LAND_LIQ > 0, ds.RIVER_DISCHARGE_OVER_LAND_LIQ, 0
        )
        ocean_dis = xr.where(
            ds.TOTAL_DISCHARGE_TO_OCEAN_LIQ > 0, ds.TOTAL_DISCHARGE_TO_OCEAN_LIQ, 0
        )
        ds = land_dis + ocean_dis
        ds = ds.where(ds > 0).to_dataset(
            name="discharge"
        )  # renaming and selecting only river discharge
    elif var == "runoff":
        ds = ds.rename({"QRUNOFF": "runoff"})[
            "runoff"
        ].to_dataset()  # renaming and selecting only runoff
    else:
        print("variable unknown")
        return None
    return ds


def create_discharge(scenario, realization):
    """
    Opens runoff and river discharge from CESM2 (according to scenario and realization), preprocesses according to preprocess_cesm.
    Saves river discharge, downscaled to daily resolution with runoff (through the function downscale).
    :param scenario: str
    :param realization: str
    """
    # translate parameters for file paths
    if scenario == "historical":
        period = "HIST"
    else:
        period = scenario
    file_real = CESM2_REALIZATION_DICT[scenario][realization]
    time_range = get_time_range(scenario)
    # === open preprocess downscale ===
    path = (
        f"/net/meso/climphys/cesm212/b.e212.B{period}cmip6.f09_g17.{file_real}/archive/"
    )
    files_dis, files_run = [], []
    for year in time_range:
        for month in [f"{m:02d}" for m in range(1, 13)]:
            files_dis.append(
                f"{path}rof/hist/b.e212.B{period}cmip6.f09_g17.{file_real}.mosart.h0.{year}-{month}.nc"
            )
        files_run.append(
            f"{path}lnd/hist/b.e212.B{period}cmip6.f09_g17.{file_real}.clm2.h6.{year}-01-01-03600.nc"
        )
    # add the last file. example: 2100-01-01 has info about 2099-12-31, so needs to be added
    year = year + 1  # year after last year in time range
    month = "01"
    files_dis.append(
        f"{path}rof/hist/b.e212.B{period}cmip6.f09_g17.{file_real}.mosart.h0.{year}-{month}.nc"
    )
    # get monthly discharge
    discharge = xr.open_mfdataset(
        files_dis, preprocess=preprocess_hydro_cesm, combine="nested"
    ).load()

    # get daily runoff
    def preprocess_runoff(ds):
        """
        Helper function because open_mfdataset wants single variable functions
        """
        return preprocess_hydro_cesm(ds, var="runoff")

    runoff = (
        xr.open_mfdataset(files_run, preprocess=preprocess_runoff, combine="nested")
        .load()
        .resample(time="1D")
        .mean()
    )
    # downscale and save
    output = get_output_path("A", scenario, realization)
    downscale(
        discharge,
        runoff,
        f"{output}/atmospheric_variables/CESM2_discharge.nc",
    )


def open_discharge(scenario, realization):
    """
    Opens and preprocesses discharge data (see function preprocess_cesm_discharge) for a certain year. If end year is passed as an int, it opens all years between year and end_year (included)
    :param scenario, realization: str
    """
    output = get_output_path("A", scenario, realization)
    filename = f"{output}/atmospheric_variables/CESM2_discharge.nc"
    try:
        ds = xr.open_dataset(filename)
    except FileNotFoundError:
        print("River discharge files not found. Creating them.")
        create_discharge(scenario, realization)
        ds = xr.open_dataset(filename)
    return ds.convert_calendar(
        "proleptic_gregorian"
    )  # new calendar to get numpy datetime (necessary for weekly resampling)


def open_era(cesm_lat, cesm_lon):
    """
    Opens ERA5 discharge, and preprocesses it to fit the naming conventions
    If the file doesn't exist, the function creates the necessary file
    """
    # ERA5 discharge for the ENTSO-e time range
    file_name = "../output/bias_correction/Raw_ERA5_discharge.nc"

    def preprocess_era(ds):
        """
        changes variable names to fit CESM2 standard, and changes lat order to go from 90->-90 to -90->90
        :param ds: dataset
        :param cesm_lat: latitude grid of CESM2,
        """
        ds = ds.rename({"latitude": "lat", "longitude": "lon", "dis24": "discharge"})
        ds = ds.reindex(lat=ds.lat[::-1])
        ds_co = ds.coarsen(lat=10, lon=10, boundary="trim").sum()
        ds_co = select_Europe(ds_co)
        # since the ERA5 grid is exactly 10 higher resolution than CESM2, the two grids should have the same length after selecting Europe. However, there might be slight differences in the absolute values of the grids (lat = 30.2 instead of 30.25) due to the coarsening. That is why we assign the lat and lon values of CESM2 here.
        if len(ds_co.lat) == len(cesm_lat) and len(ds_co.lon) == len(cesm_lon):
            ds_co["lat"] = cesm_lat
            ds_co["lon"] = cesm_lon
        else:
            print("Error: CESM2 and ERA5 grid are not same length")
        return ds_co

    try:
        ds_era5 = xr.open_dataset(file_name)
    except FileNotFoundError:
        print("ERA5 discharge files not found. Creating them.")
        files = [
            f"../inputs/ERA5/discharge_{year}.nc" for year in range(1995, 2023)
        ]  # historical+calbration ERA5 data
        ds_era5 = xr.open_mfdataset(files, preprocess=preprocess_era, combine="nested")
        ds_era5.to_netcdf(f"../output/bias_correction/Raw_ERA5_discharge.nc")

    return ds_era5


def resample_weekly(ds, time_range=[]):
    """
    Opens a dataset ds and resamples it to weekly time resolution.
    If time range isn't empty (and has a start and end date), it opens only the time range (plus a week) for resampling.
    :param ds: xarray dataset
    :param time_range: list (empty if not used)
    """
    if len(time_range) == 2:
        ds = ds.sel(
            time=slice(
                time_range[0] + pd.Timedelta(days=0),
                time_range[1] + pd.Timedelta(days=7),
            )
        )  # open the right time range
    ds_weekly = ds.resample(time="1W", origin="start").sum()
    ds_weekly["time"] = ds_weekly.time - pd.Timedelta(
        days=6
    )  # set labels t0 match inflow
    ds_weekly["time"] = ds_weekly.indexes[
        "time"
    ].normalize()  # remove time component (sub-daily) of datetime
    return ds_weekly


def open_entsoe(tech):
    """
    Opens the ENTSO-e data for the technology specified (either inflow or ror)
    :param tech: string
    """
    if tech == "inflow":
        ds = open_entsoe_inflow()
    elif tech == "ror":
        ds = open_entsoe_ror()
    else:
        print("Technology not recognized. Please choose 'inflow' or 'ror'")
    return scale_up(ds, tech)


def open_discharge_entsoe_for_calibration(era5_discharge, tech):
    """
    Opens ENTSO-e data, and adds the corresponding era5 discharge data into the same xarray dataset
    """
    # ENTSO-e
    calibration_ds = open_entsoe(tech)  # conversion data set for inflows/ror
    # ERA5 discharge
    [start, end] = (
        calibration_ds.groupby("time.year").sum().year[[0, -1]].values
    )  # for calibration, we only use the years available from ENTSO-e for ERA5
    era_discharge_for_calibration = era5_discharge.sel(
        time=slice(str(start), str(end))
    )["discharge"].sel(country=calibration_ds.country)
    if tech == "inflow":
        time_range = calibration_ds.time[
            [0, -1]
        ].values  # find values of start and end date, to open era5 weekly correctly
        era_discharge_for_calibration = resample_weekly(
            era_discharge_for_calibration, time_range=time_range
        )  # get era5 in weekly resolution
    if tech == "ror":
        era_discharge_for_calibration["time"] = (
            calibration_ds.time
        )  # ensuring same time stamp (discharge resamples to 11.30 every day and not 00.00)
    calibration_ds["discharge"] = era_discharge_for_calibration
    return calibration_ds


def read_entso_countries(tech):
    """
    Reads the list of countries for which ENTSO-e data is available for the technology specified.
    :param tech: string
    """

    folder_path = f"../inputs/entsoe_{tech}/"

    # read all the folders in the path. Each folder corresponds to a country
    country_list = [
        folder
        for folder in os.listdir(folder_path)
        if os.path.isdir(os.path.join(folder_path, folder))
    ]

    return country_list, folder_path


def open_entsoe_ror():
    """
    Opens the ENTSO-e data for the ror technology.
    """
    year_0 = 2017
    year_N = 2022

    # read all the folders in the path. Each folder corresponds to a country
    country_list, folder_path = read_entso_countries("ror")

    years = range(year_0, year_N + 1)

    ds_ror = []

    for country in country_list:
        ds_time = []
        for year in years:
            # Load data
            df_ror_full = pd.read_csv(
                folder_path
                + country
                + "/Actual Generation per Production Type_"
                + str(year)
                + "01010000-"
                + str(year + 1)
                + "01010000.csv"
            )

            # Convert date to datetime and delta_time (the MTU column has this format:"01.01.2022 00:00 - 01.01.2022 01:00 (CET/CEST)")
            df_ror_full["time"] = df_ror_full["MTU"].apply(
                lambda x: dt.datetime(
                    year=int(x[6:10]), month=int(x[3:5]), day=int(x[0:2])
                )
            )
            df_ror_full["delta_time"] = df_ror_full["MTU"].apply(
                lambda x: (
                    dt.datetime.strptime(
                        x.split(" - ")[1].split(" ")[0]
                        + " "
                        + x.split(" - ")[1].split(" ")[1],
                        "%d.%m.%Y %H:%M",
                    )
                    - dt.datetime.strptime(x.split(" - ")[0], "%d.%m.%Y %H:%M")
                ).total_seconds()
                / 3600
            )

            # Calculate GWh per each time step
            df_ror_full["ror_GWh"] = (
                df_ror_full["Hydro Run-of-river and poundage  - Actual Aggregated [MW]"]
                * df_ror_full["delta_time"]
                / 1000
            )

            # Group ror production by date
            ds_time.append(
                df_ror_full[["ror_GWh", "time"]].groupby("time").sum().to_xarray()
            )
        ds_ror.append(xr.concat(ds_time, dim="time"))
    ds_ror = xr.concat(ds_ror, dim="country")
    ds_ror["country"] = country_list

    return ds_ror


def create_entsoe_inflow():
    """
    This function reads the ENTSO-e data for the inflow technology (from the folder inputs/entsoe_inflow), and creates a dataset with the inflow values.
    The inflow values are calculated as the sum of the generation and the change in filling level of the reservoirs, based on the energy balance of the reservoir.
    Due to low quality of the public data, the inflow values are adjusted in two steps:
    1. The filling level values are adjusted to remove outliers
    2. The inflow values are adjusted to remove negative values
    The function saves the dataset with the inflow values in the folder inputs/entsoe_inflow.

    ds_raw is the dataset with the raw inflow values, and ds_adj is the dataset with the adjusted inflow values.
    """
    ## CREATE TIME DATAFRAME ##

    year_0 = 2016
    year_N = 2023

    start_date = dt.datetime(year_0, 1, 4)
    end_date = dt.datetime(year_N, 12, 25)

    dates = pd.date_range(start_date, end_date, freq="1W-MON")
    df_time = pd.DataFrame(
        {
            "date": dates,
            "week": dates.isocalendar().week,
            "year": dates.isocalendar().year,
        }
    )
    df_time = df_time.reset_index().drop(columns="index")

    ## COUNTRY LIST ##
    country_list, folder_path = read_entso_countries("inflow")

    ## CREATE EMPTY DATASET ##
    # Create the placeholder data function
    def create_placeholder_data():
        return np.full((len(country_list), len(df_time)), np.nan)

    ds_raw = xr.Dataset(
        coords={"country": country_list, "time": df_time.date},
        data_vars={
            x: (["country", "time"], create_placeholder_data())
            for x in ["V", "gen", "delta_V", "inflow_GWh"]
        },
    )

    ## READ FILLING LEVELS ##
    for country in tqdm(country_list, desc="Reading filling levels per country"):
        filename = f"../inputs/entsoe_inflow/{country}/Water Reservoirs and Hydro Storage Plants_201412290000-202412300000.csv"
        df_V = pd.read_csv(filename)
        V_list = []
        # Compile filling levels for each year and interpolate missing values
        for year in range(year_0, year_N + 1):
            mask = df_V.columns.str.contains(str(year))
            V_list.extend(
                df_V.loc[: len(df_time[df_time.year == year]) - 1, mask]
                .interpolate()
                .copy()
                .values.flatten()
                / 1000
            )
        # Add filling levels to dataset
        ds_raw["V"].loc[{"country": country}] = xr.DataArray(V_list, dims=("time"))

    # Calculate the change in filling level (Delta V)
    ds_raw["delta_V"] = ds_raw["V"].diff("time")
    ds_raw["delta_V"] = ds_raw["delta_V"].shift(time=-1)

    ## READ GENERATION ##
    date_format = "%d.%m.%Y %H:%M"

    for country in tqdm(country_list, desc="Reading reservoir generation per country"):
        df_gen = pd.DataFrame(columns=["time", "gen_GWh"])
        # Compile generation for each year and interpolate missing values
        for year in range(year_0, year_N + 1):
            filename = f"../inputs/entsoe_inflow/{country}/Actual Generation per Production Type_{str(year)}01010000-{str(year+1)}01010000.csv"
            df_gen_year = pd.read_csv(filename)
            df_gen_year = df_gen_year.interpolate()
            df_gen_year["time"] = df_gen_year["MTU"].apply(
                lambda x: dt.datetime.strptime(x[:15], date_format)
            )
            df_gen_year["time_delta"] = (
                df_gen_year.time.shift(-1) - df_gen_year.time
            ).dt.total_seconds() / 3600
            df_gen_year["gen_GWh"] = (
                df_gen_year["Hydro Water Reservoir  - Actual Aggregated [MW]"]
                * df_gen_year["time_delta"]
                / 1000
            )
            df_gen = pd.concat([df_gen, df_gen_year[["time", "gen_GWh"]]], axis=0)
        # get weekly data
        sum_gen = resample_weekly(
            df_gen.set_index("time").to_xarray().sortby("time").gen_GWh,
            [
                df_time["date"].iloc[0],
                df_time["date"].iloc[-1],
            ],  # to get the right time range
        )
        # Add generation to dataset
        ds_raw["gen"].loc[{"country": country}] = xr.DataArray(sum_gen, dims=("time"))

    ## CALCULATE INFLOW ##
    eff = 0.9**0.5  # roundtrip efficiency of the hydro power plant assumed to be 90%
    ds_raw["inflow_GWh"] = (
        ds_raw["gen"] / eff  # energy that left the reservoir to generate electricity
        + ds_raw["delta_V"]  # energy that entered via water flowing into reservoir
    )

    ## ADJUST INFLOW LEVELS ##

    ## 1. IDENTIFY WRONG FILLING LEVEL VALUES ##
    # Calculate the ratio of the change in filling level to the maximum generation in the week
    ds_raw["ratio_dV_maxGen"] = ds_raw["delta_V"] / ds_raw["gen"].max("time")
    # Create a copy of the dataset
    ds_adj = ds_raw.copy()

    ratio_threshold = 1

    # Remove filling level outliers, identified where the delta_V is greater than the maximum generation (i.e. ratio_dV_maxGen > -1)
    ds_raw["ratio_dV_maxGen"] = ds_raw["ratio_dV_maxGen"].shift(time=1)
    ds_adj["V"] = ds_adj["V"].where(ds_raw["ratio_dV_maxGen"] > -ratio_threshold)
    ds_raw["ratio_dV_maxGen"] = ds_raw["ratio_dV_maxGen"].shift(time=-1)

    # Interpolate missing values
    ds_adj["V"] = ds_adj.V.interpolate_na(dim="time", method="linear")

    # Re-calculate the change in filling level and inflow
    ds_adj["delta_V"] = ds_adj["V"].shift(time=-1) - ds_adj["V"]
    ds_adj["inflow_GWh"] = ds_adj["gen"] / eff + ds_adj["delta_V"]

    ## 2. REMOVE NEGATIVE INFLOW VALUES ##
    ds_adj["inflow_GWh"] = ds_adj["inflow_GWh"].where(ds_adj["inflow_GWh"] >= 0, 0)

    ## OUTPUT DATASET AND REVOME UNNECESSARY VARIABLES ##
    ds = ds_adj.copy()
    ds = ds.drop_vars(["V", "gen", "delta_V", "ratio_dV_maxGen"])

    ds.to_netcdf("../inputs/entsoe_inflow/entsoe_inflow.nc")
    return None


def open_entsoe_inflow():
    file = glob.glob("../inputs/entsoe_inflow/entsoe_inflow.nc")
    if file == []:
        create_entsoe_inflow()
        file = glob.glob("../inputs/entsoe_inflow/entsoe_inflow.nc")
    ds_inflow = xr.open_dataset(file[0])

    return ds_inflow


# ==================================
# === AGGREGATION AND CONVERSION ===
# ==================================


def weighted_aggregation(ds_discharge, tech):
    """
    Aggregates the discharge data to country level, using the JRC dataset as a reference for the weighting coefficients.
    """

    # Create a dataset with the normalized installed capacity of ror power plants per country
    lat = ds_discharge.lat.values
    lon = ds_discharge.lon.values
    lat_edge = (lat[:-1] + lat[1:]) / 2
    lon_edge = (lon[:-1] + lon[1:]) / 2
    lon_edge = np.insert(lon_edge, 0, -1000)
    lon_edge = np.append(lon_edge, 1000)
    lat_edge = np.insert(lat_edge, 0, 0)
    lat_edge = np.append(lat_edge, 1000)

    # Load the JRC dataset
    file_path = "../inputs/jrc-hydro-power-plant-database.csv"
    df_jrc = pd.read_csv(file_path)
    country_code_list = df_jrc["country_code"].unique().tolist()
    country_name_list = [
        country_code_to_country_name(country_code) for country_code in country_code_list
    ]

    file_name = f"../inputs/normalized_capacity_{tech}.nc"
    try:
        ds_C = xr.open_dataset(file_name)
    except FileNotFoundError:
        print(
            "normalized capacity "
            + tech
            + " dataset does not exist. Start computing it."
        )
        # Define the type of power plants to consider
        if tech == "ror":
            type_code = ["HROR"]
        elif tech == "inflow":
            type_code = ["HDAM", "HPHS"]

        # Create the dataset
        ds_C = xr.Dataset(
            data_vars=dict(
                normalized_capacity=(
                    ["lat", "lon", "country"],
                    np.zeros((len(lat), len(lon), len(country_name_list))),
                ),
            ),
            coords=dict(country=country_name_list, lat=lat, lon=lon),
            attrs=dict(description="Installed hydro capacity (normalized per country)"),
        )

        # Fill the dataset
        for country_code, country_name in zip(country_code_list, country_name_list):
            Capacities_JRC = np.zeros((len(lat), len(lon)))
            for ii in range(len(lon)):
                for jj in range(len(lat)):
                    Capacities_JRC[jj, ii] = df_jrc["installed_capacity_MW"][
                        (df_jrc["type"].isin(type_code))  # correct technologie
                        & (
                            df_jrc["country_code"] == country_code
                        )  # belongs to correct country
                        & (
                            lon_edge[ii] < df_jrc["lon"]
                        )  # this and next 3 lines: lies within the currently considered grid box
                        & (df_jrc["lon"] < lon_edge[ii + 1])
                        & (lat_edge[jj] < df_jrc["lat"])
                        & (df_jrc["lat"] < lat_edge[jj + 1])
                    ].sum()
            # Normalize capacities such that sum over each country yields one
            ds_C.normalized_capacity.loc[{"country": country_name}] = (
                Capacities_JRC[:, :]
                / df_jrc["installed_capacity_MW"][
                    (df_jrc["type"].isin(type_code))
                    & (df_jrc["country_code"] == country_code)
                ].sum()
            )
        ds_C.to_netcdf(file_name)
        print("Normalized capacity " + tech + " dataset saved")

    # Calculate the discharge per country
    ds_discharge_weighted = []
    for country in country_name_list:
        ds = (
            ds_C.normalized_capacity.sel(country=country) * ds_discharge.discharge
        ).sum(("lat", "lon"))
        ds_discharge_weighted.append(ds)

    ds_discharge_weighted = xr.concat(ds_discharge_weighted, dim="country")
    ds_discharge_weighted = ds_discharge_weighted.to_dataset(name="discharge")

    return ds_discharge_weighted


def piecewise_linear(x, a1, b1, a2, b2, q):
    return np.piecewise(
        x, [x <= q, x > q], [lambda x: a1 * x + b1, lambda x: a2 * x + b2]
    )


def objective(params, x, y, q):
    (
        a1,
        b1,
        a2,
    ) = params
    b2 = a1 * q + b1 - a2 * q  # Ensure continuity at x = 10
    y_fit = piecewise_linear(x, a1, b1, a2, b2, q)
    return np.sum((y - y_fit) ** 2)


def get_pwlf(calibration_ds, tech):
    """
    Returns the piece-wise linear regression fit for the calibration dataset, giveen a technology tech.
    :param calibration_ds: xarray dataset
    :param tech: str
    """
    # get 75th percentile
    q = calibration_ds.discharge.quantile(0.75, skipna=True).values
    # print(q)#get_qu_75(calibration_ds).values
    # calibration parameters
    calib = calibration_ds.dropna(dim="time")
    x = calib.discharge.values
    y = calib[f"{tech}_GWh"].values
    # piece-wise linear fit
    initial_guess = [1, 0, 1]  # [a1, b1, a2]
    bounds = [(0, None), (None, 0), (0, None)]
    result = minimize(objective, initial_guess, args=(x, y, q), bounds=bounds)
    # linear fit parameters
    a1_opt, b1_opt, a2_opt = result.x
    b2_opt = a1_opt * q + b1_opt - a2_opt * q

    return [a1_opt, b1_opt, a2_opt, b2_opt], q


def read_power_stats_prod(countries, tech):
    """
    Reads the annual production of hydropower for each country of interest, for the hydropower technology specified
    :param countries: list of country codes
    :param tech: string
    """
    prod_per_country = np.zeros(len(countries))
    delim = [
        ";",
        "\t",
        ",",
    ]  # different years have different delimiters for their .csv file
    time_range = range(2021, 2024)  # time range considered
    for j, year in enumerate(time_range):
        annual_prod = pd.read_csv(
            f"../inputs/entsoe_scaling/monthly_domestic_values_{year}.csv",
            delimiter=delim[j],
        )
        for i, country in enumerate(countries):
            annual_prod_country = annual_prod[
                annual_prod["Country"] == country
            ]  # choosing country
            if tech == "ror":
                # select technology and sum over months
                annual_prod_country = annual_prod_country[
                    annual_prod_country["Category"] == "Hydro Run-of-river and poundage"
                ]["ProvidedValue"].sum()
                prod_per_country[
                    i
                ] += annual_prod_country  # adding annual sum for each year
            elif tech == "inflow":
                for sub_tech in ["Hydro Water Reservoir", "Hydro Pumped Storage"]:
                    # select sub-technology and sum over months
                    annual_prod_sub_tech = annual_prod_country[
                        annual_prod_country["Category"] == sub_tech
                    ]["ProvidedValue"].sum()
                    prod_per_country[
                        i
                    ] += annual_prod_sub_tech  # adding annual sum for each year, for both subtechnologies together

    prod_per_country = prod_per_country / len(
        time_range
    )  # average to annual mean production
    # create output xarray dataarray
    prod_per_country = xr.DataArray(
        prod_per_country, dims=["country"], coords={"country": list(countries)}
    )
    return prod_per_country


def scale_up(ds, tech):
    """
    Scales output to fit average annual hydropower production values for each country
    :param ds: DataArray of transformed discharge-to-hydro, per country
    :param tech: string
    """
    annual_reported_production = read_power_stats_prod(ds.country.values, tech)
    annual_mean_production_here = ds.groupby("time.year").sum("time").mean("year")
    scaled_output = ds * (annual_reported_production / annual_mean_production_here)
    return scaled_output


def country_code_to_country_name(code):
    country_codes = {
        "CH": "Switzerland",
        "IT": "Italy",
        "FR": "France",
        "SK": "Slovakia",
        "DE": "Germany",
        "ES": "Spain",
        "AT": "Austria",
        "SI": "Slovenia",
        "SE": "Sweden",
        "UK": "United Kingdom",
        "FI": "Finland",
        "EL": "Greece",
        "RO": "Romania",
        "AL": "Albania",
        "BG": "Bulgaria",
        "HR": "Croatia",
        "PT": "Portugal",
        "MK": "Macedonia",
        "RS": "Serbia",
        "CZ": "Czech Republic",
        "ME": "Montenegro",
        "BA": "Bosnia and Herzegovina",
        "HU": "Hungary",
        "IE": "Ireland",
        "PL": "Poland",
        "BE": "Belgium",
        "LV": "Latvia",
        "LT": "Lithuania",
        "XK": "Kosovo",
        "NO": "Norway",
    }

    return country_codes[code]

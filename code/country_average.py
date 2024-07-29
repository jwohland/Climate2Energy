import salem
import xarray as xr


def get_country_list():
    """
    List of countries that are included in energy models from
    Leonard Goeke and Jonas Savelsberg
    :return:
    """

    countries = {
        "Albania": "AL",
        "Austria": "AT",
        "Bosnia and Herzegovina": "BA",
        "Belgium": "BE",
        "Bulgaria": "BG",
        "Switzerland": "CH",
        "Czech Republic": "CZ",
        "Germany": "DE",
        "Denmark": "DK",
        "Estonia": "EE",
        "Spain": "ES",
        "Finland": "FI",
        "France": "FR",
        "Greece": "GR",
        "Croatia": "HR",
        "Hungary": "HU",
        "Ireland": "IE",
        "Italy": "IT",  # several bidding zones
        "Lithuania": "LT",
        "Latvia": "LV",
        "Montenegro": "ME",
        "Macedonia": "MK",
        "Netherlands": "NL",
        "Norway": "NO",  # several bidding zones
        "Poland": "PL",
        "Portugal": "PT",
        "Romania": "RO",
        "Serbia": "RS",
        "Sweden": "SE",  # several bidding zones
        "Slovenia": "SI",
        "Slovakia": "SK",
        "United Kingdom": "UK",
    }
    return countries


def cut_out_countries(ds):
    """
    Split global input dataset per country.
    :param ds: dataset with new dimension country
    :return:
    """
    shdf = salem.read_shapefile(salem.get_demo_file("world_borders.shp"))
    ds_list = []
    for country in get_country_list():
        shdf_tmp = shdf.loc[shdf["CNTRY_NAME"] == country]
        ds_country = ds.salem.roi(shape=shdf_tmp, all_touched=True)
        ds_country["country"] = country
        ds_list.append(ds_country)
    return xr.concat(ds_list, dim="country")


def cut_out_countries_offshore(ds):
    """
    Split datasset per country via Exclusive Economic Zones.

    This function is similar to
        cut_out_countries(ds)
    but has subtle differences in how the shapefile is treated.

    :param ds:
    :return:
    """
    shdf = read_EEZ_shapefile()
    ds_list = []
    for country in shdf.index:
        shdf_tmp = shdf.loc[country]
        ds_country = ds.salem.roi(geometry=shdf_tmp.geometry, all_touched=True)
        ds_country["country"] = country
        ds_list.append(ds_country)
    return xr.concat(ds_list, dim="country")


def read_EEZ_shapefile():
    """
    Opens shapefile of Exclusive Economic Zones and prepares them for country
    subsetting.
    :return:
    """
    shdf = salem.read_shapefile("../inputs/EEZ/eez_v11.shp").set_index(
        "TERRITORY1"
    )  # sortby country name
    shdf = shdf[shdf.GEONAME.str.contains("Exclusive")]
    shdf["geometry"] = shdf.simplify(
        tolerance=0.5, preserve_topology=True
    )  # reduce shapefile resolution to approx half the model resolution
    countries = get_country_list()
    countries_EEZ = [
        x for x in countries if x in shdf.index
    ]  # only countries with coast
    shdf = shdf.loc[countries_EEZ]
    return shdf


def country_means(ds, method="median_and_better", onshore=True):
    """
    Aggregate over a country

    Method "all" takes an unweighted mean over all boxes within a country

    Method "median_and_better" (the default) takes an unweighted mean over all boxes in a country
    with average capacity factors that are at least as high as the median over the country.

    :param ds:
    :return:
    """
    ds = ds.transpose(..., "lat", "lon")  # salem needs [lat, lon] as last coordinates
    if onshore:
        ds = cut_out_countries(ds)
    else:
        ds = cut_out_countries_offshore(ds)
    if method == "all":
        ds = ds.mean(dim=["lat", "lon"], skipna=True)
    elif method == "median_and_better":
        ref = ds.mean(dim="time", skipna=True).median(
            dim=["lat", "lon"], skipna=True
        )  # median per country
        ds = ds.where(ds.mean(dim=["time"], skipna=True) >= ref).mean(
            dim=["lat", "lon"], skipna=True
        )  # only average overlocations that at least as good as the median on average
    return ds


def store_as_pandas_dataframe(da, name):
    """
    Save dataarray da as pandas dataFrame to output directory
    :param ds:
    :param name:
    :return:
    """
    da.to_pandas().to_csv("../output/" + name + ".csv")

import salem
import xarray as xr


def get_country_list():
    """
    List of countries that are included in energy models from
    Leonard Goeke and Jonas Savelsberg
    :return:
    """
    countries = [
        "Albania",
        "Austria",
        "Bosnia and Herzegovina",
        "Belgium",
        "Bulgaria",
        "Switzerland",
        "Czech Republic",
        "Germany",
        "Denmark",
        "Estonia",
        "Spain",
        "Finland",
        "France",
        "Greece",
        "Croatia",
        "Hungary",
        "Ireland",
        "Italy",
        "Lithuania",
        "Latvia",
        "Montenegro",
        "Macedonia",
        "Netherlands",
        "Norway",
        "Poland",
        "Portugal",
        "Romania",
        "Serbia",
        "Sweden",
        "Slovenia",
        "Slovakia",
        "United Kingdom",
    ]
    return countries


def cut_out_countries(ds):
    """
    Split global input dataset per country.
    #todo add similar computation for offshore wind
    :param ds: dataset with new dimension country
    :return:
    """
    shdf = salem.read_shapefile(salem.get_demo_file("world_borders.shp"))
    ds_list = []
    for country in get_country_list():
        print(country)
        shdf_tmp = shdf.loc[shdf["CNTRY_NAME"] == country]
        ds_country = ds.salem.roi(shape=shdf_tmp, all_touched=True)
        ds_country["country"] = country
        ds_list.append(ds_country)
    return xr.concat(ds_list, dim="country")


def country_means(ds, method="above_median"):
    """
    Aggregate over a country

    Method "all" takes an unweighted mean over all boxes within a country

    Method "above_median" (the default) takes an unweighted mean over all boxed in a country
    that are better than the median on average.

    :param ds:
    :return:
    """
    ds = ds.transpose(..., "lat", "lon")  # salem needs [lat, lon] as last coordinates
    ds = cut_out_countries(ds)
    if method == "all":
        ds = ds.mean(dim=["lat", "lon"], skipna=True)
    elif method == "above_median":
        ref = ds.median(dim=["lat", "lon", "time"], skipna=True)  # median per country
        ds = ds.where(ds.mean(dim=["time"], skipna=True) > ref).mean(
            dim=["lat", "lon"], skipna=True
        )  # only average over locations that are better than the median on average
    return ds


def store_as_pandas_dataframe(da, name):
    """
    Save dataarray da as pandas dataFrame to output directory
    :param ds:
    :param name:
    :return:
    """
    da.to_pandas().to_csv("../output/" + name + ".csv")

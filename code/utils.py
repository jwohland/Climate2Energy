def zero_mean_longitudes(ds):
    """
    resort a dataset with longitudes from
        0 to 360
    to one that has longitudes from
        -180 to 180
    :param ds:
    :return:
    """
    ds.coords['lon'] = (ds.coords['lon'] + 180) % 360 - 180
    ds = ds.sortby("lon")
    return ds

def store_as_pandas_dataframe(ds, name):
    """

    :param ds:
    :param name:
    :return:
    """
    ds.to_pandas().to_csv("../output/" + name + ".csv")


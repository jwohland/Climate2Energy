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

def temp_cel(ds):
    """
    returns the temperature dataset ds in celsius
    """
    if "temperature" in ds.data_vars:
        ds["temperature"] = ds["temperature"] - 273.15
        return ds 
    else:
        "temperature is not in this dataset"
        return None
from bias_correction import BiasCorrection
import subprocess
import glob


def bias_correct(da, var, method, lat, lon):
    """takes a data array da of a chosen variable var, and returns the
    bias corrected version (using package bias_correction)."""
    # making sure that the reference and model data is available
    if (
        glob.glob(f"../output/{var}_ERA5.nc") == []
        or glob.glob(f"../output/hist_{var}.nc") == []
    ):
        subprocess.run("./preprocess_bias_correction.sh")
    # open reference and model data
    reference = xr.open_dataset(f"../output/{var}_ERA5.nc").TREFHT
    model = xr.open_dataset(f"/../output/hist_{var}.nc").TREFHT.sel(
        lat=slice(30, 75), lon=slice(-15, 50)
    )
    # finding grid cell and converting to Pandas.Series (necessary for bias_correction package)
    ls = [reference, model, da]
    for i in range(len(ls)):
        ls[i] = ls[i].sel(lat=lat, lon=lon, method="nearest").to_series()
    # bias_correction
    bc = BiasCorrection(ls[0], ls[1], ls[2])
    corrected = bc.correct(method=method)

    # - Delta correction (i.e., multiplying with scalar such that means are the same in model and "truth")
    # - Quantile matching
    # - CDFt
    return corrected.to_xarray()

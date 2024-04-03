import xarray as xr
from bias_correction import BiasCorrection
import subprocess
import glob
from utils import *
import numpy as np
import pandas as pd
from utils import interpolate_wind_xr, find_height


def bias_correct_per_loc(reference, model, da, method="basic_quantile"):
    """
    Computes bias correction using the model output during historical period (model)
    and the ground truth (reference) and applies  the correction to future model output (da).

    reference, model and da have to be xr.DataArrays at a single location


    """
    if np.isnan(da).all():
        return da
    else:
        bc = BiasCorrection(pd.Series(reference), pd.Series(model), pd.Series(da))
        return bc.correct(method=method)


def bias_correct_dataset(ds, var, method="basic_quantile"):
    """
    takes a data array da of a chosen variable var, and returns the
    bias corrected version (using package bias_correction).

    """
    ref_file = f"../output/{var}_ERA5.nc"
    mod_file = f"../output/hist_{var}.nc"
    # making sure that the reference and model data is available
    if glob.glob(ref_file) == []:
        print(f"missing reference ground truth file {var}")
        subprocess.run(["bash", f"preprocess/preprocess_{var}_ERA5.sh"])
    if glob.glob(mod_file) == []:
        print(f"missing historical model file for {var}")
        subprocess.run(["bash", f"preprocess/preprocess_{var}_model_hist.sh"])
    # open reference and model data
    reference = zero_mean_longitudes(xr.open_dataset(ref_file))
    model = zero_mean_longitudes(xr.open_dataset(mod_file))
    if var == "s_hub":
        # get height information
        model["Z3"] = zero_mean_longitudes(xr.open_dataset("../output/hist_Z3.nc"))[
            "Z3"
        ]
        model = find_height(model)
        model = interpolate_wind_xr(model, output_height=100)[
            0
        ]  # we want only s_hub, not the alpha parameter here
    # the reference dataset has slightly different values for the dimension "lat" (max 10E-14) due to different segmentation in cdo/python. this fixes it
    reference["lat"] = model.lat
    # bias_correction
    corrected = xr.apply_ufunc(
        bias_correct_per_loc,
        reference[var].load(),
        model[var].load(),
        ds[var].load(),
        vectorize=True,
        input_core_dims=[["time"], ["time"], ["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[["time"]],
        kwargs={"method": method},
    )
    corrected["time"] = ds["time"]  # to restore time coordinate in dataarray
    return corrected.squeeze()

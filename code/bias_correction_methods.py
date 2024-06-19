import xarray as xr
from bias_correction import BiasCorrection
import subprocess
import glob
from utils import *
import numpy as np
import pandas as pd
from utils import interpolate_wind_xr, find_height
from downscaling_discharge import downscale


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

def bias_correct_hydro(ds, ref, hist, method="basic_quantile"):
    """
    bias correction for hydro. bias corrects over time for each country present in the thre datasets
    
    """
    corrected = xr.apply_ufunc(
        bias_correct_per_loc,
        ref,
        hist,
        ds,
        vectorize=True,
        input_core_dims=[["time"], ["time"], ["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[["time"]],
        kwargs={"method": method},
    )
    corrected["time"] = ds["time"]  # to restore time coordinate in dataarray
    return corrected.squeeze()


def prepare_bias_correction(bc_realization):
    """
    Prepare bias correction input files using CESM2 realization
    bc_realization and ERA5.

    Internally, this loops over temperature, global_horizontal and s_hub

    :param bc_realization: A, B, C
    :return:
    """
    for var in ["temperature", "global_horizontal", "s_hub"]:
        ref_file = f"../output/bias_correction/Raw_ERA5_{var}.nc"
        mod_file = f"../output/bias_correction/{bc_realization}/Raw_CESM2_{var}_{bc_realization}.nc"
        if glob.glob(ref_file) == []:
            print(f"missing historical ERA5 file for {var}")
            subprocess.run(
                ["bash", f"preprocess/preprocess_{var}_ERA5.sh"]
            )
        if glob.glob(mod_file) == []:
            print(f"missing historical model file for {var} for historical realization {bc_realization}")
            bc_identifier = CESM2_REALIZATION_DICT["historical"][bc_realization]
            subprocess.run(
                ["bash", f"preprocess/preprocess_{var}_CESM2.sh", bc_realization, bc_identifier]
            )

def bias_correct_dataset(ds, var, bc_realization, method="basic_quantile"):
    """
    takes a data array da of a chosen variable var, and returns the
    bias corrected version (using package bias_correction).

    """
    ref_file = f"../output/bias_correction/Raw_ERA5_{var}.nc"
    mod_file = f"../output/bias_correction/{bc_realization}/Raw_CESM2_{var}_{bc_realization}.nc"
    # making sure that the reference and model data is available
    if glob.glob(ref_file) == []:
        print(f"missing reference ground truth file {var}")
        subprocess.run(["bash", f"preprocess/preprocess_{var}_ERA5.sh"])
    if glob.glob(mod_file) == []:
        print(f"missing historical model file for {var}")
        subprocess.run(["bash", f"preprocess/preprocess_{var}_model_hist.sh"])
        if var == "discharge":
            subprocess.run(["bash", f"preprocess/preprocess_runoff_model_hist.sh"])
            ds_discharge = xr.open_dataset(f'../output/hist_discharge_monthly.nc')
            ds_runoff = xr.open_dataset(f"../output/hist_runoff.nc")
            downscale(ds_discharge,ds_runoff,"hist_discharge") #downscale from monthly to daily discharge values using daily runoff 
    # open reference and model data
    reference = zero_mean_longitudes(xr.open_dataset(ref_file))
    model = zero_mean_longitudes(xr.open_dataset(mod_file))
    if var == "s_hub":
        # get height information
        model["Z3"] = zero_mean_longitudes(
            xr.open_dataset(
                f"../output/bias_correction/{bc_realization}/Raw_CESM2_Z3_{bc_realization}.nc"
            )
        )["Z3"]
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

from utils_plot import *
import xarray as xr


def get_data_path(scenario):
    data_path = f"../output/bias_correction/A/{scenario}/A/output_variables/"
    return data_path


def open_data_as_dictionary():
    # Choose median turbine
    turbine = "SWT120_3600"

    ds_dict = {}
    for scenario in ["historical", "SSP370"]:
        ds_dict[scenario] = {}
        if scenario == "historical":
            time_range = range(1995, 2015)

        else:
            time_range = range(2080, 2100)
        for density_correct in [True, False]:
            if density_correct:
                file_ending = "_density-corrected.nc"
            else:
                file_ending = ""
            ds_list = [
                xr.open_dataset(
                    get_data_path(scenario) + f"Wind-power_{year}{file_ending}"
                )
                for year in time_range
            ]
            print(get_data_path(scenario) + f"Wind-power_1995{file_ending}")
            ds = xr.concat(ds_list, dim="time")
            ds_dict[scenario][density_correct] = ds.sel(turbine=turbine)
            print("Done")
    return ds_dict


ds_dict = open_data_as_dictionary()

##########################
# First plot: Absolute CFs
##########################
f, axs = plt.subplots(ncols=2, nrows=2, figsize=(8, 6), **SUBPLOT_KW)
cbar_ax = f.add_axes([0.2, 0.1, 0.6, 0.02])

cbar_kwargs = {
    "label": "Capacity factor",
    "orientation": "horizontal",
}

for i, scenario in enumerate(["historical", "SSP370"]):
    for j, density_correct in enumerate([True, False]):
        ax = axs[j, i]
        ds = ds_dict[scenario][density_correct]
        ds.mean(dim="time")["CF_wind"].plot(
            ax=ax,
            vmin=0,
            vmax=0.6,
            levels=13,
            cmap="Oranges",
            cbar_ax=cbar_ax,
            cbar_kwargs=cbar_kwargs,
        )
        add_coast_boarders(ax)
        ax.set_title(scenario + " & " + str(density_correct))

add_letters(axs, x=-0.04, y=1.05)
plt.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.15)
plt.savefig("../plots/paper/density/Mean_CF_maps_density_effect.jpeg", dpi=300)

##########################
# Second plot: Density CF differences
##########################
f, axs = plt.subplots(ncols=3, nrows=1, figsize=(14, 4), **SUBPLOT_KW)
cbar_ax = f.add_axes([0.2, 0.12, 0.6, 0.02])

cbar_kwargs = {
    "label": "Change in capacity factor (with - without density correction)",
    "orientation": "horizontal",
}

for i, scenario in enumerate(["historical", "SSP370"]):
    add_coast_boarders(axs[i])
    ds_diff_density = (ds_dict[scenario][True] - ds_dict[scenario][False]).mean(
        dim="time"
    )
    ds_diff_density["CF_wind"].plot(
        ax=axs[i],
        vmin=-0.03,
        vmax=0.03,
        levels=7,
        cmap="coolwarm",
        cbar_ax=cbar_ax,
        cbar_kwargs=cbar_kwargs,
    )
    axs[i].set_title(scenario)

# Add difference between both
i = 2
add_coast_boarders(axs[i])

ds_diff_density_hist = ds_dict["historical"][True].mean(dim="time") - ds_dict[
    "historical"
][False].mean(dim="time")
ds_diff_density_SSP370 = ds_dict["SSP370"][True].mean(dim="time") - ds_dict["SSP370"][
    False
].mean(dim="time")
ds_diff = ds_diff_density_hist - ds_diff_density_SSP370

ds_diff["CF_wind"].plot(
    ax=axs[i],
    vmin=-0.05,
    vmax=0.05,
    levels=11,
    cmap="coolwarm",
    cbar_ax=cbar_ax,
    cbar_kwargs=cbar_kwargs,
)
axs[i].set_title("historical - SSP370")

add_letters(axs, x=-0.04)
plt.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.15)
plt.savefig("../plots/paper/density/Diff_CF_maps_density_effect.jpeg", dpi=300)


##########################
# Third plot: CC CF differences with / without density correction
##########################
f, axs = plt.subplots(ncols=3, nrows=1, figsize=(14, 4), **SUBPLOT_KW)
cbar_ax = f.add_axes([0.2, 0.12, 0.6, 0.02])

cbar_kwargs = {
    "label": "Change in capacity factor (SSP370 - historical)",
    "orientation": "horizontal",
}

for i, density_correct in enumerate([True, False]):
    add_coast_boarders(axs[i])
    ds_diff_CC = ds_dict["SSP370"][density_correct].mean(dim="time") - ds_dict[
        "historical"
    ][density_correct].mean(dim="time")
    ds_diff_CC["CF_wind"].plot(
        ax=axs[i],
        vmin=-0.05,
        vmax=0.05,
        levels=11,
        cmap="coolwarm",
        cbar_ax=cbar_ax,
        cbar_kwargs=cbar_kwargs,
    )
    axs[i].set_title(density_correct)

# Add difference between both
i = 2
add_coast_boarders(axs[i])

ds_diff_CC_True = ds_dict["SSP370"][True].mean(dim="time") - ds_dict["historical"][
    True
].mean(dim="time")
ds_diff_CC_False = ds_dict["SSP370"][False].mean(dim="time") - ds_dict["historical"][
    False
].mean(dim="time")
ds_diff = ds_diff_CC_True - ds_diff_CC_False

ds_diff["CF_wind"].plot(
    ax=axs[i],
    vmin=-0.05,
    vmax=0.05,
    levels=11,
    cmap="coolwarm",
    cbar_ax=cbar_ax,
    cbar_kwargs=cbar_kwargs,
)
axs[i].set_title("True - False")

add_letters(axs, x=-0.04)
plt.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.15)
plt.savefig("../plots/paper/density/Diff_CF_maps_CC_effect.jpeg", dpi=300)

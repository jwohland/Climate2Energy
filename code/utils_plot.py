import pandas as pd
from utils import get_output_path
import glob
import seaborn as sns
import matplotlib.pyplot as plt
import pickle
import string
import cartopy.crs as ccrs
import cartopy.feature as cf

tech_filter_dict = {
    "PV": "PV*",
    "SWT_120_onshore": "*SWT120*onshore_True*",
    "SWT_120_offshore": "*SWT120*onshore_False*",
    "SWT_142_onshore": "*SWT142*onshore_True*",
    "SWT_142_offshore": "*SWT142*onshore_False*",
    "E-126_onshore": "*E-126*onshore_True*",
    "E-126_offshore": "*E-126*onshore_False*",
    "heating": "heating*",
    "cooling": "cooling*",
    "Hydropower (dam)": "hydro_inflow*",
    "Hydropower (ror)": "hydro_ror*",
}

df_colors = pd.DataFrame(
    {
        "PV": "#d5c200",
        "Wind onshore": "#518696",
        "Wind offshore": "#215968",
        "Hydropower (dam)": "#6782e4",
        "Hydropower (ror)": "#00125e",
        "heating": "#780015",
        "cooling": "#007d95",
    },
    index=["color"],
)


def get_tech_timeseries_dictionary(tech_filter_dict):
    """

    Open timeseries of both scenarios and all combinations for
    the technologies defined in the input dictionary

    :param tech_filter_dict:
    :return:
    """
    df_dict = {}
    for scenario in ["historical", "SSP370"]:
        df_dict[scenario] = {}
        for tech in tech_filter_dict.keys():
            print(tech)
            df_dict[scenario][tech] = {}
            for bc_realization in ["A", "B", "C"]:
                df_dict[scenario][tech][bc_realization] = {}
                for realization in ["A", "B", "C"]:
                    # Open csv file
                    csv_path = (
                        get_output_path(bc_realization, scenario, realization)
                        + "output_variables/"
                    )
                    filenames = glob.glob(csv_path + tech_filter_dict[tech] + ".csv")
                    filenames = [name for name in filenames if "boost" not in name]  # remove boosted simulations of they exist
                    df = pd.concat(
                            [
                                pd.read_csv(filename, index_col=0)
                                for filename in sorted(filenames)
                            ],
                            axis=1,
                        )
                    df_dict[scenario][tech][bc_realization][realization] = df
    return df_dict


def combine_wind(df_dict, location="onshore"):
    """
    Combine all onshore or offshore turbines by computing the mean over the
    3 turbines
    :param df_dict: dictionary with timeseries and this structure
    :param location: "onshore" or "offshore"
    :return:
    """
    for scenario in ["historical", "SSP370"]:
        df_dict[scenario][f"Wind {location}"] = {}
        for bc_realization in ["A", "B", "C"]:
            df_dict[scenario][f"Wind {location}"][bc_realization] = {}
            for realization in ["A", "B", "C"]:
                df_mean = (
                    1
                    / 3
                    * (
                        df_dict[scenario][f"SWT_120_{location}"][bc_realization][
                            realization
                        ]
                        + df_dict[scenario][f"SWT_142_{location}"][bc_realization][
                            realization
                        ]
                        + df_dict[scenario][f"E-126_{location}"][bc_realization][
                            realization
                        ]
                    )
                )
                df_dict[scenario][f"Wind {location}"][bc_realization][
                    realization
                ] = df_mean
    return df_dict


def compute_metrics_all_sims(metrics=["mean", "q05", "q95"]):
    """
    Computes different statistical metrics for all simulations and
    outputs a dictionary of pandas dataframes
    :param metrics:
    :return:
    """
    filename = "../output/metrics_all_sims.pkl"
    try:  # check if already computed
        with open(filename, "rb") as f:
            df_dict = pickle.load(f)
    except FileNotFoundError:
        df_dict = {}
        for scenario in ["historical", "SSP370"]:
            df_dict[scenario] = {}
            for tech in tech_filter_dict.keys():
                df_dict[scenario][tech] = {}
                df_result_list = []
                for bc_realization in ["A", "B", "C"]:
                    for realization in ["A", "B", "C"]:
                        # Open csv file
                        csv_path = (
                            get_output_path(bc_realization, scenario, realization)
                            + "output_variables/"
                        )
                        filenames = glob.glob(csv_path + tech_filter_dict[tech] + ".csv")
                        filenames = [name for name in filenames if "boost" not in name]  # remove boosted simulations of they exist
                        df = pd.concat(
                            [
                                pd.read_csv(filename, index_col=0)
                                for filename in sorted(filenames)
                            ],
                            axis=1,
                        )
                        # Compute metricc
                        for metric in metrics:
                            if metric == "mean":
                                df_result = df.mean(axis=1)
                            else:
                                q = float(metric[1:]) / 100
                                df_result = df.quantile(q=q, axis=1)
                            df_result = df_result.to_frame(
                                bc_realization + realization + metric
                            )
                            df_result_list.append(df_result)
                df_results = pd.concat(df_result_list, axis=1)
                # Column names are AAmean, AAq05 etc. now and we re-arrange them to
                # different levels in the dictionary and then we only use AA, AB, AC..
                # as column names
                for metric in metrics:
                    mask = df_results.columns.str.contains(metric)
                    df_masked = df_results.loc[:, mask]
                    df_dict[scenario][tech][metric] = df_masked.rename(
                        columns={x: x[0:2] for x in df_masked.columns}
                    )
        with open(filename, "wb") as f:
            pickle.dump(df_dict, f)
    df_dict = unify_hydro_country_names(df_dict)
    return df_dict


def unify_hydro_country_names(df_dict):
    """
    Currently the hydropower country codes (2 letter) are different from the rest (full names).
    This function aligns them and should become obsolete in future versions of the code.


    :param df_dict:
    :return:
    """
    unify_country_names = {
        "AT": "Austria",
        "BG": "Bulgaria",
        "CH": "Switzerland",
        "DE": "Germany",
        "ES": "Spain",
        "FR": "France",
        "IT": "Italy",
        "ME": "Montenegro",
        "NO": "Norway",
        "PT": "Portugal",
        "RO": "Romania",
        "SE": "Sweden",
    }
    for scenario in ["SSP370", "historical"]:
        for tech in ["Hydropower (dam)", "Hydropower (ror)"]:
            for metric in ["mean", "q05", "q95"]:
                df_dict[scenario][tech][metric].rename(
                    unify_country_names, inplace=True
                )
    return df_dict


def combine_dictionary_dataframe(df_dict):
    df_aggregate = pd.DataFrame.from_dict(
        {
            (scenario, technology, metric, bc_realization): df_dict[scenario][
                technology
            ][metric][bc_realization]
            for scenario in df_dict.keys()
            for technology in df_dict["SSP370"].keys()
            for metric in df_dict["SSP370"]["PV"].keys()
            for bc_realization in df_dict["SSP370"]["PV"]["mean"].keys()
        },
        orient="index",
    )
    df_aggregate.index.rename(
        ["Scenario", "Technology", "Metric", "bc_realization"], inplace=True
    )
    return df_aggregate


def compute_delta_CF(df_aggregate, relative=False):
    """
    Build dataframe with changes in capacity factor calculated as

    delta CF = CF(tech, SSP370, bc_realization, realization)
        -  CF(tech, SSP370, bc_realization, bc_realization)

    Thinking is that over the historical period, bc_realization and realization should
    be the same but not in the future since the scenarios don't correspond to the
    same runs. This is to avoid double counting of variability.

    :param df_res:
    :param relative:
    :return:
    """
    delta_CF_list = []
    for tech in df_aggregate.index.levels[1]:
        for metric in df_aggregate.index.levels[2]:
            df_res = df_aggregate.query(f"Metric=='{metric}' & Technology=='{tech}'")
            for bc_realization in ["A", "B", "C"]:
                df_hist = df_res.query(
                    f"Scenario=='historical' & bc_realization=='{bc_realization}{bc_realization}'"
                )
                for future_realization in ["A", "B", "C"]:
                    df_fut = df_res.query(
                        f"Scenario=='SSP370' & bc_realization in '{bc_realization}{future_realization}'"
                    )
                    df_diff = df_fut.reset_index(drop=True) - df_hist.reset_index(
                        drop=True
                    )
                    if relative:
                        df_diff /= df_hist.reset_index(drop=True)
                        df_diff *= 100  # in percent
                    df_diff["Technology"] = tech
                    df_diff["Metric"] = metric
                    df_diff["bc_realization"] = bc_realization
                    df_diff["future_realization"] = future_realization
                    df_diff = df_diff.set_index(
                        ["Technology", "Metric", "bc_realization", "future_realization"]
                    )
                    delta_CF_list.append(df_diff)
    df_delta_CF = pd.concat(delta_CF_list)
    return df_delta_CF


def plot_mean_heatmap(
    df,
    filename,
    title,
    cmap=sns.color_palette("YlOrBr", as_cmap=True),
    center=None,
    label="",
    folder="effect_of_climate_variability",
):
    """
    Plot heatmap of mean
    :param df:
    :param filename:
    :param title:
    :param cmap:
    :param center:
    :param label:
    :param folder:
    :return:
    """
    f, ax = plt.subplots(figsize=(12, 6))
    plt.subplots_adjust(bottom=0.35, left=0.08, right=0.95, top=0.93)
    cbar_ax = f.add_axes([0.25, 0.1, 0.5, 0.03])
    sns.heatmap(
        df.transpose(),
        ax=ax,
        cmap=cmap,
        center=center,
        cbar_ax=cbar_ax,
        cbar_kws={"orientation": "horizontal", "label": label},
    )
    ax.set_xlabel("")
    ax.set_ylabel("Combination of bc_realization and realization")
    ax.set_title(title)
    plt.savefig(f"../plots/generation/{folder}/{filename}.jpeg", dpi=300)


def plot_difference_relative_heatmap(
    df,
    filename,
    title,
    cmap=sns.color_palette("vlag", as_cmap=True),
    center=0,
    folder="effect_of_climate_variability",
):
    # Plot relative difference to mean
    f, ax = plt.subplots(figsize=(12, 6))
    plt.subplots_adjust(bottom=0.35, left=0.08, right=0.95, top=0.93)
    cbar_ax = f.add_axes([0.25, 0.1, 0.5, 0.03])
    df_mean_relative = (df.div(df.mean(axis=1), axis=0) - 1) * 100
    sns.heatmap(
        df_mean_relative.transpose(),
        ax=ax,
        cmap=cmap,
        center=center,
        cbar_ax=cbar_ax,
        cbar_kws={"orientation": "horizontal", "label": "Difference to mean [%]"},
    )
    ax.set_xlabel("")
    ax.set_ylabel("Combination of bc_realization and realization")
    ax.set_title(title)
    plt.savefig(f"../plots/generation/{folder}/{filename}.jpeg", dpi=300)


# todo move this into make_plots.py
if __name__ == "__main__":
    df_dict = compute_metrics_all_sims()
    ################
    # Means and relative difference due to variability
    ################
    for scenario in df_dict.keys():
        for tech in df_dict["historical"].keys():
            for metric in df_dict["historical"]["PV"].keys():
                df_tmp = df_dict[scenario][tech][metric]
                plot_mean_heatmap(
                    df_tmp, f"{metric}_{tech}_{scenario}", f"{tech} {scenario} {metric}"
                )
                plot_difference_relative_heatmap(
                    df_tmp,
                    f"{metric}_relative_difference_{tech}_{scenario}",
                    f"{tech} {scenario} {metric}",
                )
                plt.close()  # avoid cluttering
    ################
    # Means and relative difference due to change
    ################
    for tech in df_dict["historical"].keys():
        for metric in df_dict["historical"]["PV"].keys():
            df_historical = df_dict["historical"][tech][metric].mean(axis=1)
            df_future = df_dict["SSP370"][tech][metric].mean(axis=1)
            df_diff = df_future - df_historical
            plot_kwargs = {
                "cmap": sns.color_palette("vlag", as_cmap=True),
                "center": 0,
                "folder": "effect_of_climate_change",
            }
            plot_mean_heatmap(
                df_diff.to_frame("mean absolute difference"),
                f"CC_{metric}_{tech}",
                f"{tech} {scenario} {metric}",
                label="Absolute difference",
                **plot_kwargs,
            )
            plt.close()
            df_diff_rel = df_diff / df_historical * 100
            plot_mean_heatmap(
                df_diff_rel.to_frame("mean relative difference [%]"),
                f"CC_{metric}_{tech}_relative",
                f"{tech} {scenario} {metric}",
                label="Relative difference [%]",
                **plot_kwargs,
            )
            plt.close()  # avoid cluttering

    ################
    # Means per country in seperate plots
    ################
    df_aggregate = combine_dictionary_dataframe(df_dict)
    for country in df_aggregate.columns:
        for metric in ["mean", "q05", "q95"]:
            f, axs = plt.subplots(ncols=2, figsize=(12, 4))
            df_res = df_aggregate.query(
                f"Metric=='{metric}' & Technology not in ['heating', 'cooling']"
            )[country].reset_index()

            sns.barplot(
                df_res,
                x="Technology",
                hue="Scenario",
                y=country,
                ax=axs[0],
                errorbar=("pi", 99),
            )  # errorbars show max-min range
            df_heat = df_aggregate.query(
                f"Metric=='{metric}' & Technology in ['heating', 'cooling']"
            )[country].reset_index()
            sns.barplot(
                df_heat,
                x="Technology",
                hue="Scenario",
                y=country,
                ax=axs[1],
                errorbar=("pi", 99),
            )  # errorbars show max-min range
            for i in range(2):
                axs[i].tick_params(axis="x", rotation=90)
                axs[i].set_xlabel("")
                axs[i].set_ylabel("")
            axs[0].legend_.remove()
            plt.tight_layout()
            plt.suptitle(f"{country} and {metric}")
            plt.subplots_adjust(top=0.9)
            plt.savefig(
                f"../plots/generation/country_assessment/{country}_{metric}.jpeg",
                dpi=300,
            )
            plt.close()

    ################
    # Scatter plots CV vs. CC
    ################
    for relative in [True, False]:
        df_delta_CF = compute_delta_CF(df_aggregate, relative=relative)
        for country in df_delta_CF.columns:
            f, axs = plt.subplots(ncols=2, figsize=(12, 5))
            sns.boxplot(
                df_delta_CF.query(
                    "Technology not in ['heating', 'cooling']"
                ).reset_index(),
                y="Technology",
                x=country,
                hue="Metric",
                ax=axs[0],
            )
            sns.boxplot(
                df_delta_CF.query("Technology in ['heating', 'cooling']").reset_index(),
                y="Technology",
                x=country,
                hue="Metric",
                ax=axs[1],
            )
            axs[0].set_title("Generation")
            axs[1].set_title("Demand")
            for i in range(2):
                axs[i].set_xlabel("")
                axs[i].set_ylabel("")
                axs[i].axvline(x=0, ls="--", color="grey")
            plt.suptitle(country)
            plt.tight_layout()
            filename = f"{country}_signal-to-noise_"
            if relative:
                filename += "relative"
            else:
                filename += "absolute"
            plt.savefig(
                f"../plots/generation/country_assessment/{filename}.jpeg", dpi=300
            )
            plt.close()


def add_letters(ax, x=-0.08, y=1.02, fs=10, letter_offset=0):
    """
    adds bold letters a,b,c,... to the upper left corner of subplots
    :param ax: axis
    :param x: x location of text
    :param y: ylocation of text
    :param fs: fontsize
    :return:
    """
    letters = list(string.ascii_lowercase)
    try:
        ax.flat
        for il, tmp_ax in enumerate(ax.flat):
            tmp_ax.text(
                x,
                y,
                letters[il + letter_offset],
                weight="bold",
                horizontalalignment="center",
                verticalalignment="center",
                transform=tmp_ax.transAxes,
                fontsize=fs,
            )
    except AttributeError:
        ax.text(
            x,
            y,
            letters[letter_offset],
            weight="bold",
            horizontalalignment="center",
            verticalalignment="center",
            transform=ax.transAxes,
            fontsize=fs,
        )


SUBPLOT_KW = {"subplot_kw": {"projection": ccrs.PlateCarree()}}


def add_coast_boarders(ax):
    ax.add_feature(cf.COASTLINE)
    ax.add_feature(cf.BORDERS)
    ax.gridlines()

from utils_plot import *
import seaborn as sns


def compute_correlation(scenario, focus_tech, df_dict_combined, correlate_with):
    """
    Compute correlations between country-level generation  and
    - demand-weighted European mean generation
    - unweighted European mean generation
    - European heating and cooling demand

    :param scenario:
    :param focus_tech:
    :param df_dict_combined:
    :param correlate_with:
    :return:
    """
    df_dict_tmp = df_dict_combined[scenario][focus_tech]
    corr_list = []
    for realization in ["A", "B", "C"]:
        for bc_realization in ["A", "B", "C"]:
            if correlate_with == "demand_weighted_mean_generation":
                # Compute weights
                df_heat_mean = df_dict[scenario]["heating"][realization][
                    bc_realization
                ].mean(axis=1)
                df_cool_mean = df_dict[scenario]["cooling"][realization][
                    bc_realization
                ].mean(axis=1)
                df_demand = df_heat_mean + df_cool_mean
                df_weight = df_demand / df_demand.sum()
                weighted_mean = (
                    df_dict_tmp[realization][bc_realization]
                    .multiply(df_weight, axis=0)
                    .sum(axis=0)
                )
                corr_list.append(
                    df_dict_tmp[realization][bc_realization].corrwith(
                        weighted_mean, axis=1
                    )
                )
            elif correlate_with == "mean_generation":
                mean = df_dict_tmp[realization][bc_realization].sum(
                    axis=0
                )  # Mean over countries
                corr_list.append(
                    df_dict_tmp[realization][bc_realization].corrwith(mean, axis=1)
                )
            elif correlate_with == "total_demand":
                df_heat_Europe_ts = df_dict[scenario]["heating"][realization][
                    bc_realization
                ].mean(
                    axis=0
                )  # timeseries of European mean heating demand
                df_cool_Europe_ts = df_dict[scenario]["cooling"][realization][
                    bc_realization
                ].mean(
                    axis=0
                )  # timeseries of European mean cooling demand
                df_demand_Europe_ts = df_heat_Europe_ts + df_cool_Europe_ts
                corr_list.append(
                    df_dict_tmp[realization][bc_realization].corrwith(
                        df_demand_Europe_ts, axis=1
                    )
                )
    df_corr = pd.concat(corr_list, axis=1)
    return df_corr


# Load data
df_dict = get_tech_timeseries_dictionary(tech_filter_dict)
df_dict_with_onshore = combine_wind(df_dict, "onshore")
df_dict_combined = combine_wind(df_dict_with_onshore, "offshore")


# Make actual plots

for correlate_with in [
    "demand_weighted_mean_generation",
    "mean_generation",
    "total_demand",
]:
    # Calculate difference in correlation
    diff_list = []
    for focus_tech in [
        "Wind onshore",
        "Wind offshore",
        "PV",
        "Hydropower (ror)",
        "Hydropower (dam)",
    ]:
        df_corr_hist = compute_correlation(
            "historical", focus_tech, df_dict_combined, correlate_with
        )
        df_corr_future = compute_correlation(
            "SSP370", focus_tech, df_dict_combined, correlate_with
        )
        diff = (df_corr_future.mean(axis=1) - df_corr_hist.mean(axis=1)).to_frame(
            name=focus_tech
        )
        diff_list.append(diff)
    diffs = pd.concat(diff_list, axis=1)

    # Plotting
    f, ax = plt.subplots(ncols=1, figsize=(10, 12))
    cbar_ax = f.add_axes([0.25, 0.05, 0.7, 0.02])
    sns.heatmap(
        diffs.sort_values(by="Wind onshore", ascending=False),
        ax=ax,
        vmin=-0.05,
        vmax=0.05,
        annot=True,
        fmt=".2f",
        cmap=sns.color_palette("coolwarm", n_colors=10),
        cbar_kws={
            "label": "Change in Pearson correlation (SSP370 - historical)",
            "orientation": "horizontal",
        },
        cbar_ax=cbar_ax,
    )
    ax.set_ylabel("")
    plt.subplots_adjust(bottom=0.1, left=0.25, right=0.9, top=0.98)
    plt.savefig(
        f"../plots/paper/correlation/correlation_change_{correlate_with}.jpeg", dpi=300
    )
    plt.close()

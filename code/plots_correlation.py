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
    df_corr = pd.concat(corr_list, axis=1)
    return df_corr


# Load data
df_dict = get_tech_timeseries_dictionary(tech_filter_dict)
df_dict_with_onshore = combine_wind(df_dict, "onshore")
df_dict_combined = combine_wind(df_dict_with_onshore, "offshore")

# Define country subset to be shown in reduced plots
country_subset = [
    "United Kingdom",
    "Poland",
    "Germany",
    "Italy",
    "France",
    "Spain",
    "Norway",
    "Greece",
]

# Make actual plots

for correlate_with in [
    "demand_weighted_mean_generation",
    "mean_generation",
]:
    # Calculate difference in correlation and agreement on sign of change
    diff_list = []
    agree_list = []
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
        N_same_sign = ((df_corr_future - df_corr_hist) > 0).sum(axis=1)
        agree_list.append(N_same_sign.to_frame(name=focus_tech))
    diffs = pd.concat(diff_list, axis=1)
    agreement = pd.concat(agree_list, axis=1)

    # Plotting
    diffs = diffs.sort_values(by="Wind onshore", ascending=False)
    for all_countries in [True, False]:
        if all_countries:
            figsize=(10, 12)
            bottom = 0.2
            rotation=90
            left = .25
            bottom_colorbar = 0.05
        else:
            figsize=(10,6)
            bottom = 0.28
            rotation=45
            left = .13
            bottom_colorbar = 0.07

        f, ax = plt.subplots(ncols=1, figsize=figsize)
        cbar_ax = f.add_axes([0.25, bottom_colorbar, 0.7, 0.02])

        for threshold in range(10):
            if threshold in [9, 0]:
                annot_kws ={"weight": "bold"}
            else:
                annot_kws = {}
            diffs_tmp = diffs[agreement == threshold]
            if not all_countries:
                diffs_tmp = diffs_tmp.loc[country_subset]
            sns.heatmap(
                diffs_tmp,
                ax=ax,
                vmin=-0.08,
                vmax=0.08,
                annot=True,
                fmt=".2f",
                annot_kws=annot_kws,
                cmap=sns.color_palette("coolwarm", n_colors=16),
                cbar_kws={
                    "label": "Correlation change relative to European mean (SSP370 - historical)",
                    "orientation": "horizontal",
                },
                cbar_ax=cbar_ax,
            )

        ax.set_ylabel("")
        plt.subplots_adjust(bottom=bottom, left=left, right=0.95, top=0.98)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=rotation);
        plt.savefig(
            f"../plots/paper/correlation/correlation_change_{correlate_with}_all_{all_countries}.jpeg", dpi=300
        )
        plt.close()

from utils_plot import *


def rolling_cyclic(df):
    """
    Take 20y timeseries and turn into annual cycle
    using 4 week rolling mean over the days
    :param df:
    :return:
    """
    df_daily = df.groupby(df.index.day_of_year).mean()
    n_window = 28  # 4 week rolling mean
    # Repeat data at beginning and end of year to mimic cycle behaviour
    # Example: 3 day centered running mean on Jan 1st includes Dec 31st
    for added_day in range(1, int(n_window / 2)):
        df_daily.loc[366 + added_day] = df_daily.loc[added_day]
        df_daily.loc[1 - added_day] = df_daily.loc[366 - added_day]
    df_daily.sort_index(inplace=True)
    df_daily_rolling = df_daily.rolling(n_window, center=True).mean().dropna()
    df_daily_rolling.index = pd.period_range(
        "2000-01-01", freq="D", periods=365
    ).strftime("%d.%m.")
    return df_daily_rolling


def convert_hydro_units(df_dict):
    """
    Convert hydro from "GWh per week for inflow and per day for ror" to GW
    """
    for experiment in ["historical", "SSP370"]:
        for rea in ["A", "B", "C"]:
            for rea_b in ["A", "B", "C"]:
                df_dict[experiment]["Hydropower (ror)"][rea][rea_b] /= 24
                df_dict[experiment]["Hydropower (dam)"][rea][rea_b] /= (24 * 7)
    return df_dict



df_dict = get_tech_timeseries_dictionary(tech_filter_dict)
# Add offshore and onshore
df_dict = combine_wind(df_dict, "onshore")  # mean over 3 turbines
df_dict = combine_wind(df_dict, "offshore")  # mean over 3 turbines
# Unit conversion of hydropower.
df_dict = convert_hydro_units(df_dict)


# todo remove everything that follows this if once country names have been aligned
if 1 == 1:
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

    for experiment in ["historical", "SSP370"]:
        for rea in ["A", "B", "C"]:
            for rea_b in ["A", "B", "C"]:
                try:
                    df_dict[experiment]["Hydropower (ror)"][rea][rea_b].rename(
                        unify_country_names, inplace=True
                    )
                    df_dict[experiment]["Hydropower (dam)"][rea][rea_b].rename(
                        unify_country_names, inplace=True
                    )
                except:
                    print("")

countries = list(df_dict["SSP370"]["PV"]["A"]["A"].index)

ylabels = {
    "PV": "PV Capacity Factor",
    "heating": "Heating demand [GW]",
    "cooling": "Cooling demand [GW]",
    "Wind": "Wind Capacity Factor",
    "Hydropower (ror)": "Hydropower ror generation [GW]",
    "Hydropower (dam)": "Hydropower inflow [GW]",
}

tech_panel_mapping = {
    "PV": 0,
    "Wind onshore": 1,
    "Wind offshore": 1,
    "Hydropower (dam)": 2,
    "Hydropower (ror)": 2,
    "heating": 3,
    "cooling": 3,
}

for country in countries:
    # Prepare figure
    f, axs = plt.subplots(nrows=4, figsize=(8, 10))
    ax_ror = axs[2].twinx()
    ax_cooling = axs[3].twinx()

    for tech in tech_panel_mapping.keys():
        i_tech = tech_panel_mapping[tech]
        color = df_colors[tech].values[0]
        # Choose axis to plot on
        ax = axs[i_tech]
        if tech == "cooling":
            ax = ax_cooling
        if tech == "Hydropower (ror)":
            ax = ax_ror

        try:  # statement needed because not all countries feature all technologies
            # Compute dataframes with all 9 scenarios
            hist_list, fut_list = [], []
            for bc_realization in ["A", "B", "C"]:
                for realization in ["A", "B", "C"]:
                    df_hist = (
                        df_dict["historical"][tech][bc_realization][realization]
                        .loc[country]
                        .transpose()
                    )
                    df_hist.index = pd.to_datetime(df_hist.index)
                    hist_list.append(df_hist)
                    df_fut = (
                        df_dict["SSP370"][tech][bc_realization][realization]
                        .loc[country]
                        .transpose()
                    )
                    df_fut.index = pd.to_datetime(df_fut.index)
                    fut_list.append(df_fut)
            df_hist = pd.concat(hist_list, axis=1)
            df_fut = pd.concat(fut_list, axis=1)

            for i_plot, df in enumerate([df_hist, df_fut]):
                ls = ["solid", "--"][i_plot]
                if i_tech == 0:
                    label = ["historical", "SSP370"][i_plot]
                elif (tech.split(" ")[0] == "Wind") and (i_plot == 0):
                    label = tech.split(" ")[1]
                else:
                    label = None

                df_daily_rolling = rolling_cyclic(df)
                # plot means
                df_daily_rolling.mean(axis=1).plot(
                    ax=ax,
                    color=color,
                    alpha=0.8,
                    label=label,
                    ls=ls,
                    xticks=[0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 304, 335],
                )
                # plot uncertainty bands
                ax.fill_between(
                    df_daily_rolling.min(axis=1).index,
                    df_daily_rolling.min(axis=1),
                    df_daily_rolling.max(axis=1),
                    alpha=0.15,
                    color=color,
                    ls=ls,
                )
                xlabel = ""
                ax.set_xlim(xmin=-0.1, xmax=366.1)
                ax.set_xticklabels(
                    [
                        "Jan",
                        "Feb",
                        "Mar",
                        "Apr",
                        "May",
                        "Jun",
                        "Jul",
                        "Aug",
                        "Sep",
                        "Oct",
                        "Nov",
                        "Dec",
                    ]
                )
            try:
                label_temp = ylabels[tech.split(" ")[0]]
            except:
                label_temp = ylabels[tech]
            ax.set_ylabel(label_temp, fontdict={"color": color})
        except KeyError:
            print(f"{country} has no {tech}")
    axs[0].legend(ncol=2, bbox_to_anchor=(1, 1.2), loc=1)
    axs[1].legend(loc="lower right")
    axs[0].set_title(country)
    axs[3].set_xlabel(xlabel)
    add_letters(axs, x=-0.03, y=1.04)
    plt.tight_layout()
    fname = f"../plots/generation/cycles/seasonal_cycle_{country}_mean"
    plt.savefig(fname + ".jpeg", dpi=300)
    plt.close()

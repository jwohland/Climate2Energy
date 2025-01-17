import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cf
from matplotlib.patches import Rectangle
from utils_plot import *


# Location of country centers
center_dict = {
    "Albania": (19.37, 40.36, 1.59),
    "Austria": (12.17 + 1, 46.54, 2.35),
    "Bosnia and Herzegovina": (16.46, 42.7, 2.43),
    "Belgium": (3.57, 49.6, 1.8),
    "Bulgaria": (24.14, 41.39, 3),
    "Switzerland": (7.34 - 0.5, 45.93 - 0.5, 3.2),
    "Czech Republic": (14.36, 48.7, 3.5),
    "Germany": (6.95, 47.66, 7.0),
    "Denmark": (10.19 - 2, 54.72, 2.87),
    "Estonia": (24.05, 57.63, 2.7),
    "Spain": (-14.19 + 7, 28.44 + 8, 8),
    "Finland": (20.92 + 1, 60.32 - 1, 9.26),
    "France": (-2.16, 41.85, 8.75),
    "Greece": (20.68, 35.16, 6.25),
    "Croatia": (14.6, 42.6 + 1, 3),
    "Hungary": (18.23 - 1, 45.89 - 0.5, 2.55),
    "Ireland": (-10.01, 51.64, 3.54),
    "Italy": (7.87, 37.17, 9.4),
    "Lithuania": (22.73 - 1, 54.02, 3.2),
    "Latvia": (23.52 + 2, 55.8 - 0.3, 3),
    "Montenegro": (18.65 - 0.3, 41.93 - 0.2, 1.54),
    "Macedonia": (21.07, 40.93, 1.35),
    "Netherlands": (4.05 + 0.3, 50.89 + 0.2, 2.48),
    "Norway": (11.92 - 8, 58.65, 8),
    "Poland": (16.52 - 1, 49.29 + 1, 6),
    "Portugal": (-23.02 + 12, 33.11 + 4, 6),
    "Romania": (22.88, 43.85, 4.18),
    "Serbia": (19.03 - 0.4, 42.13 + 1, 3.77),
    "Sweden": (11.76, 56.32 + 2, 9),
    "Slovenia": (14.34 - 1, 45.5 - 0.5, 1.31),
    "Slovakia": (18.86 - 1, 47.83 - 0.3, 1.68),
    "United Kingdom": (-8.1, 50.71, 9.33),
}

iso_dict = {
    "Albania": "AL",
    "Austria": "AT",
    "Bosnia and Herzegovina": "BA",
    "Belgium": "BE",
    "Bulgaria": "BG",
    "Switzerland": "CH",
    "Czech Republic": "CZ",
    "Germany": "DE",
    "Denmark": "DK",
    "Estonia": "EE",
    "Spain": "ES",
    "Finland": "FI",
    "France": "FR",
    "Greece": "GR",
    "Croatia": "HR",
    "Hungary": "HU",
    "Ireland": "IE",
    "Italy": "IT",
    "Lithuania": "LT",
    "Latvia": "LV",
    "Montenegro": "ME",
    "Macedonia": "MK",
    "Netherlands": "NL",
    "Norway": "NO",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Serbia": "RS",
    "Sweden": "SE",
    "Slovenia": "SI",
    "Slovakia": "SK",
    "United Kingdom": "GB",
}


def spider_on_ax(df, ax, add_labels=False):
    """
    Make polar plot with changes per technology
    :param df: data
    :param ax: subplot
    :param add_labels: if True plots example plot for the legend
    :return:
    """
    delta_theta = 2 * np.pi / df.index.size
    for i_loc, tech in enumerate(df.index):
        theta = delta_theta * i_loc
        ax.bar(
            theta,
            df.iloc[i_loc]["Change"] - 100,
            bottom=100,
            width=0.7,
            color=df.iloc[i_loc]["color"],
            yerr=[[df.iloc[i_loc]["Error_minus"]], [df.iloc[i_loc]["Error_plus"]]],
            error_kw={"elinewidth": 5, "ecolor": "grey"},
        )
        if df.iloc[i_loc]["Change"] > 200:  # very large values are capped and annotated
            ax.text(
                theta - delta_theta * 0.2,
                160,
                f'+{int(df.iloc[i_loc]["Change"] - 100)}%',
                color="black",
            )
    ax.set_thetagrids(
        [360 / df.index.size * i for i in range(df.index.size)], df.index, color="black"
    )
    ax.set_ylim(ymin=0, ymax=200)
    lw_ticks = 4
    if add_labels:
        ax.set_yticks([50, 150], minor=True, alpha=0.8, lw=lw_ticks)
        ax.set_yticks([100], "")
        ax.grid(axis="x", alpha=0, color="Olive")
        for x in [delta_theta * (0.5 + n) for n in range(df.index.size)]:
            ax.axvline(x=x, color="grey", ls="--")
        # Add arrows to explain grid
        # demand
        ax.annotate(
            "",
            xy=(delta_theta * 5.5, 150),
            xytext=(delta_theta * 5.5, 100),
            arrowprops={"width": 2, "headwidth": 10, "color": "red"},
        )
        ax.text(delta_theta * 5.5, 50, "-50%", color="blue", fontsize=9)
        ax.annotate(
            "",
            xy=(delta_theta * 5.5, 50),
            xytext=(delta_theta * 5.5, 100),
            arrowprops={"width": 2, "headwidth": 10, "color": "blue"},
        )
        ax.text(delta_theta * 5.0, 150, "+50%", color="red")
        # supply
        ax.annotate(
            "",
            xy=(delta_theta * 3.5, 150),
            xytext=(delta_theta * 3.5, 100),
            arrowprops={"width": 2, "headwidth": 10, "color": "red"},
        )
        ax.text(delta_theta * 3.3, 80, "-5%", color="blue", fontsize=9)
        ax.annotate(
            "",
            xy=(delta_theta * 3.5, 50),
            xytext=(delta_theta * 3.5, 100),
            arrowprops={"width": 2, "headwidth": 10, "color": "blue"},
        )
        ax.text(delta_theta * 3.4, 160, "+5%", color="red", fontsize=9)
        # ax.arrow(delta_theta * 3.5, 100, 0, 80, color="red", zorder=100, lw=3, width=.035)
        # matplotlib.pyplot.arrow(x, y, dx, dy, **kwargs)
    else:
        ax.set_yticks([50, 150], minor=True)
        ax.set_yticks([100], labels="")
        ax.grid(axis="x", alpha=1, color="Olive")
        ax.set_xticks([])
    # Add grey background to flag demand
    ax.bar(delta_theta * 5.5, 200, bottom=10, width=1.8, color="grey", alpha=0.3)
    ax.grid(which="minor", alpha=0.7, lw=1.5)
    ax.grid(which="major", axis="y", alpha=1, color="black", lw=1.5)


def add_coast_boarders(ax):
    ax.add_feature(cf.COASTLINE, alpha=0.7, color="grey")
    ax.add_feature(cf.BORDERS, alpha=0.4, color="grey", ls="--")
    ax.add_feature(cf.LAND, alpha=0.8)
    ax.add_feature(cf.OCEAN, alpha=0.2)


def plot_dummy_rose():
    # Dummy data for explanation plot percent change per tech
    df = pd.DataFrame(
        {
            "PV": 120,
            "Wind onshore": 90,
            "Wind offshore": 95,
            "Hydropower (dam)": 108,
            "Hydropower (ror)": 120,
            "heating": 50,
            "cooling": 200,
        },
        index=["Change"],
    )
    df = df.transpose()
    df["Error_minus"] = [20, 5, 5, 8, 12, 10, 0]
    df["Error_plus"] = [10, 15, 10, 20, 20, 20, 0]
    df["color"] = df_colors.transpose()
    df.rename(index={"heating": "Heating", "cooling": "Cooling"}, inplace=True)
    # Make and save legend plot
    fig, ax = plt.subplots(
        figsize=(4, 4), subplot_kw={"projection": "polar", "frame_on": False}
    )
    spider_on_ax(df, ax, add_labels=True)
    plt.tight_layout()
    fig.savefig("../plots/paper/roses/rose_legend.png", dpi=300, transparent=True)


def plot_roses():
    """
    Loop over all countries and plot roses
    :return:
    """
    # Load data
    df_dict = compute_metrics_all_sims()
    df = combine_dictionary_dataframe(df_dict)
    df_delta_CF = compute_delta_CF(df, relative=True)

    for country in list(df_delta_CF.columns):
        change_list, error_minus_list, error_plus_list = [], [], []
        for tech in df_delta_CF.index.levels[0]:
            df_tmp = df_delta_CF.query(f"Metric=='mean' & Technology=='{tech}'")[
                country
            ]
            if tech in ["heating", "cooling"]:
                change_list.append(df_tmp.mean(axis=0) + 100)
                error_minus_list.append((df_tmp.mean(axis=0) - df_tmp.min(axis=0)))
                error_plus_list.append((df_tmp.max(axis=0) - df_tmp.mean(axis=0)))
            else:
                # To plot all changes in same rose, generation is scaled by factor of 10
                change_list.append(df_tmp.mean(axis=0) * 10 + 100)
                error_minus_list.append((df_tmp.mean(axis=0) - df_tmp.min(axis=0)) * 10)
                error_plus_list.append((df_tmp.max(axis=0) - df_tmp.mean(axis=0)) * 10)
        df_country = pd.DataFrame(
            index=df_delta_CF.index.levels[0],
            data={
                "Change": change_list,
                "Error_minus": error_minus_list,
                "Error_plus": error_plus_list,
            },
        )

        # Calculate mean onshore and offshore and delete turbine info
        df_offshore = df_country.loc[["offshore" in x for x in df_country.index]].mean(
            axis=0
        )
        df_onshore = df_country.loc[["onshore" in x for x in df_country.index]].mean(
            axis=0
        )
        df_country = df_country.transpose()
        df_country["Wind offshore"] = df_offshore
        df_country["Wind onshore"] = df_onshore
        df_country.drop(
            columns=[
                x for x in df_country.columns if "_onshore" in x or "_offshore" in x
            ],
            inplace=True,
        )

        # Add colors
        df_country = pd.concat([df_country, df_colors])

        # Align column naming to always start with capitals
        df_country.rename(
            columns={"heating": "Heating", "cooling": "Cooling"}, inplace=True
        )

        # Make sure countries without offshore domain or AC are also plotted
        if df_offshore.isna().any():
            df_country["Wind offshore"]["Change"] = 100
            df_country["Wind offshore"]["Error_minus"] = 0
            df_country["Wind offshore"]["Error_plus"] = 0
        if df_country["Cooling"].isna().any():
            df_country["Cooling"]["Change"] = 100
            df_country["Cooling"]["Error_minus"] = 0
            df_country["Cooling"]["Error_plus"] = 0

        # Sort dataframe in same order as in legend figure
        df_country = df_country[
            [
                "PV",
                "Wind onshore",
                "Wind offshore",
                "Hydropower (dam)",
                "Hydropower (ror)",
                "Heating",
                "Cooling",
            ]
        ]

        fig, ax = plt.subplots(
            figsize=(4, 4), subplot_kw={"projection": "polar", "frame_on": False}
        )
        spider_on_ax(df_country.round(2).transpose(), ax)
        plt.tight_layout()
        fig.savefig(
            f"../plots/paper/roses/{country}_rose.png",
            dpi=300,
            transparent=True,
            backend="agg",
            facecolor="none",
        )
        plt.close()


def plot_map_roses(gridlines=True):
    f, ax = plt.subplots(
        subplot_kw={"projection": ccrs.PlateCarree()}, figsize=(12, 12)
    )
    add_coast_boarders(ax)
    ax.set_extent([-11, 30, 35, 75])
    if gridlines:
        ax.gridlines(
            crs=ccrs.PlateCarree(),
            draw_labels=True,
            linewidth=2,
            color="gray",
            alpha=0.5,
            linestyle="--",
            zorder=1,
        )

    size = 10
    for country in center_dict.keys():
        image = plt.imread(f"../plots/paper/roses/{country}_rose.png")
        left, bottom, size = center_dict[country]
        if size < 2.5:
            size = 2.5
        ax.imshow(
            image,
            transform=ccrs.PlateCarree(),
            extent=(left, left + size, bottom, bottom + size),
        )
        ax.text(
            left + size / 2,
            bottom + size / 2,
            iso_dict[country],
            horizontalalignment="center",
            verticalalignment="center",
            transform=ccrs.PlateCarree(),
        )

    # Create a Rectangle patch
    left = -10.5
    bottom = 62
    size = 13
    rect = Rectangle(
        (left, bottom + 2),
        size,
        size - 2,
        linewidth=1,
        edgecolor="black",
        facecolor="white",
        transform=ccrs.PlateCarree(),
        zorder=2,
    )

    # Add the patch to the Axes
    ax.add_patch(rect)
    # Add explanation
    image = plt.imread("../plots/paper/roses/rose_legend.png")
    shrink = 0.5
    ax.imshow(
        image,
        transform=ccrs.PlateCarree(),
        extent=(
            left + shrink,
            left + size - shrink,
            bottom + shrink + 1,
            bottom + size - shrink + 1,
        ),
        zorder=3,
    )
    plt.tight_layout()
    f.savefig("../plots/paper/roses/rose_map.jpeg", dpi=300)


if __name__ == "__main__":
    plot_dummy_rose()
    plot_roses()
    plot_map_roses(gridlines=False)

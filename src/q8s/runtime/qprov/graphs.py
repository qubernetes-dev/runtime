import matplotlib.pyplot as plt
from matplotlib import colormaps


def plot_transpilation_timeline(passes, figsize=(16, 8)):
    """
    Plot a transpilation timeline.

    Parameters
    ----------
    passes : list[dict]
        List of pass execution records, e.g.

        {
            "pass_duration_s": 0.000285,
            "pass_index": 2,
            "pass_metadata": {
                "depth": 14,
                "size": 25,
                "stage": "init"
            },
            "pass_name": "HighLevelSynthesis",
            "pass_type": None
        }
    """

    passes = sorted(passes, key=lambda p: p.pass_index)

    labels = [f"{p.pass_index:03d}: {p.pass_name}" for p in passes]
    times = [p.pass_duration_s * 1000 for p in passes]
    depths = [p.pass_metadata.get("depth") for p in passes]
    sizes = [p.pass_metadata.get("size") for p in passes]
    stages = [p.pass_metadata.get("stage", "unknown") for p in passes]

    x = range(len(passes))

    fig, ax_time = plt.subplots(figsize=figsize)

    # Stage background bands
    unique_stages = list(dict.fromkeys(stages))

    cmap = colormaps["Pastel1"].resampled(max(len(unique_stages), 1))

    stage_colors = {stage: cmap(i) for i, stage in enumerate(unique_stages)}

    if stages:
        stage_start = 0
        current_stage = stages[0]

        for i, stage in enumerate(stages + [None]):
            if stage != current_stage:
                stage_end = i - 1

                ax_time.axvspan(
                    stage_start - 0.5,
                    stage_end + 0.5,
                    color=stage_colors[current_stage],
                    alpha=0.35,
                    zorder=0,
                )

                ax_time.axvline(
                    stage_start - 0.5,
                    color="gray",
                    linestyle="--",
                    linewidth=0.8,
                    alpha=0.6,
                    zorder=1,
                )

                ax_time.text(
                    (stage_start + stage_end) / 2,
                    1.02,
                    current_stage,
                    transform=ax_time.get_xaxis_transform(),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                )

                stage_start = i
                current_stage = stage

    # Runtime bars
    bars = ax_time.bar(
        x,
        times,
        alpha=0.7,
        label="Runtime",
        zorder=2,
    )

    ax_time.set_ylabel("Runtime (ms)")
    ax_time.set_xlabel("Transpiler pass")
    ax_time.set_xticks(list(x))
    ax_time.set_xticklabels(labels, rotation=60, ha="right", fontsize=8)
    ax_time.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)

    # Depth
    ax_depth = ax_time.twinx()
    depth_line = ax_depth.plot(
        list(x),
        depths,
        marker="o",
        linewidth=2,
        label="Depth",
        zorder=3,
    )
    ax_depth.set_ylabel("Circuit depth")

    # Size
    ax_size = ax_time.twinx()
    ax_size.spines["right"].set_position(("outward", 60))

    size_line = ax_size.plot(
        list(x),
        sizes,
        marker="s",
        linewidth=2,
        label="Size",
        zorder=3,
    )
    ax_size.set_ylabel("Circuit size")

    # Combined legend
    handles = [bars] + depth_line + size_line
    legend_labels = ["Runtime (ms)", "Depth", "Size"]
    ax_time.legend(handles, legend_labels, loc="upper left")

    ax_time.set_title("Transpilation Pass Timeline", pad=20)

    plt.tight_layout(rect=(0, 0.12, 1, 0.95))

    return fig

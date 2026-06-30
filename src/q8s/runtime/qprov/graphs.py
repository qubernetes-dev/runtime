import matplotlib.pyplot as plt


def plot_transpilation_timeline(passes, figsize=(16, 6)):
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
                "size": 25
            },
            "pass_name": "HighLevelSynthesis",
            "pass_type": None
        }
    """

    passes = sorted(passes, key=lambda p: p.pass_index)

    labels = [f"{p.pass_index:03d}: {p.pass_name}" for p in passes]

    times = [p.pass_duration_s * 1000 for p in passes]

    depths = [p.pass_metadata.get("depth", None) for p in passes]

    sizes = [p.pass_metadata.get("size", None) for p in passes]

    x = range(len(passes))

    fig, ax_time = plt.subplots(figsize=figsize)

    # Runtime bars
    bars = ax_time.bar(
        x,
        times,
        alpha=0.7,
        label="Runtime",
    )

    ax_time.set_ylabel("Runtime (ms)")
    ax_time.set_xlabel("Transpiler pass")
    ax_time.set_xticks(x)
    ax_time.set_xticklabels(labels, rotation=60, ha="right", fontsize=8)
    ax_time.grid(axis="y", linestyle="--", alpha=0.4)

    # Depth
    ax_depth = ax_time.twinx()
    depth_line = ax_depth.plot(
        x,
        depths,
        marker="o",
        linewidth=2,
        label="Depth",
    )
    ax_depth.set_ylabel("Circuit depth")

    # Size
    ax_size = ax_time.twinx()
    ax_size.spines["right"].set_position(("outward", 60))

    size_line = ax_size.plot(
        x,
        sizes,
        marker="s",
        linewidth=2,
        label="Size",
    )
    ax_size.set_ylabel("Circuit size")

    # Combined legend
    handles = [bars] + depth_line + size_line
    labels = ["Runtime (ms)", "Depth", "Size"]
    ax_time.legend(handles, labels, loc="upper left")

    plt.title("Transpilation Pass Timeline")
    plt.tight_layout()

    return fig

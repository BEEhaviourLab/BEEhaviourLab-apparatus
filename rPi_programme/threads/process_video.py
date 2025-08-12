from pathlib import Path
from typing import Optional, List, Dict, Tuple
import click
import polars as pl
import numpy as np
from scipy.optimize import linear_sum_assignment
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from object_detection.yolo_predict_to_file import save_bboxes_to_file

MODEL_PATH = Path("best.pt")
CONF_THRESHOLD = 0.0
XYWH = True
TRACK = True
FILTER_LABEL = 0
NUM_OBJECTS = 5
CSV1_NAME = "yolo_tracking_raw.csv"
CSV2_NAME = "yolo_tracking_velocity.csv"
CSV3_NAME = "yolo_tracking_velocity_fixed_ids.csv"


def extract_flow_info(df: pl.DataFrame, label: int) -> pl.DataFrame:
    """
    Extracts flow information from the DataFrame.

    Args:
        df (pl.DataFrame): The DataFrame containing bounding box data.
        label (int): The label to filter on.

    Returns:
        pl.DataFrame: The DataFrame with flow information, including velocity and speed.
    """
    # Filter on label
    df = df.filter(pl.col("class_id") == label)
    # If the file contains cols x1, y1, x2, y2, convert to x, y, w, h
    if "x1" in df.columns:
        df = df.with_columns(
            [
                (pl.col("x2") - pl.col("x1")).alias("w"),
                (pl.col("y2") - pl.col("y1")).alias("h"),
                # x and y are the centre of the bounding box
                (pl.col("x1") + pl.col("w") / 2).alias("x"),
                (pl.col("y1") + pl.col("h") / 2).alias("y"),
            ]
        )

    df = df.sort(["track_id", "frame_id"])

    df = df.with_columns(
        [
            (pl.col("x") - pl.col("x").shift(1)).over(["track_id"]).alias("dx"),
            (pl.col("y") - pl.col("y").shift(1)).over(["track_id"]).alias("dy"),
        ]
    )
    df = df.with_columns(
        [(pl.col("dx").pow(2) + pl.col("dy").pow(2)).sqrt().alias("speed")]
    )

    # Handle nulls
    df = df.fill_null(0)

    return df


def fix_ids(df: pl.DataFrame) -> pl.DataFrame:
    """
    Fixes the IDs in the DataFrame by assigning stable IDs to objects across frames.

    Args:
        df (pl.DataFrame): The DataFrame containing bounding box data.

    Returns:
        pl.DataFrame: The DataFrame with fixed stable IDs.
    """
    df = df.sort(["frame_id"])

    # List to store final rows (dicts)
    stable_rows: List[Dict[str, Optional[float]]] = []
    stable_id_list: List[int] = list(range(1, NUM_OBJECTS + 1))
    # Dictionary to store last known positions of stable IDs
    stable_positions: Dict[int, Optional[Tuple[float, float]]] = {
        sid: None for sid in stable_id_list
    }

    # Add "stable_id" column
    all_columns: List[str] = df.columns
    if "stable_id" not in all_columns:
        all_columns += ["stable_id"]

    # Create a list of unique frame IDs to iterate over
    frames_list: List[int] = (
        df.select(pl.col("frame_id")).unique().sort("frame_id").to_series().to_list()
    )

    for f in frames_list:
        subdf: pl.DataFrame = df.filter(pl.col("frame_id") == f)

        x_vals: np.ndarray = subdf["x"].to_numpy()
        y_vals: np.ndarray = subdf["y"].to_numpy()
        this_frame_count: int = len(x_vals)

        # Build cost matrix: shape=(num_objects, this_frame_count)
        cost: np.ndarray = np.zeros((NUM_OBJECTS, this_frame_count), dtype=np.float32)

        # Fill cost = distance from each stable ID to each detection
        for i_row, sid in enumerate(stable_id_list):
            old_pos: Optional[Tuple[float, float]] = stable_positions[sid]
            if old_pos is None:
                # Never matched this sid, put large distance to discourage matching
                old_x, old_y = 1e9, 1e9
            else:
                old_x, old_y = old_pos

            for j_col in range(this_frame_count):
                dx: float = x_vals[j_col] - old_x
                dy: float = y_vals[j_col] - old_y
                cost[i_row, j_col] = np.sqrt(dx * dx + dy * dy)

        # Hungarian assignment if detections exist
        if this_frame_count > 0:
            row_idx, col_idx = linear_sum_assignment(cost)
            # row_idx, col_idx each has length = min(num_objects, this_frame_count)
        else:
            row_idx, col_idx = [], []

        matched_sids: set[int] = set()
        matched_detections: set[int] = set()

        # Assign matched pairs
        for i_row, j_col in zip(row_idx, col_idx):
            sid: int = stable_id_list[i_row]
            matched_sids.add(sid)
            matched_detections.add(j_col)

            new_x: float = x_vals[j_col]
            new_y: float = y_vals[j_col]
            # Update stable position
            stable_positions[sid] = (new_x, new_y)

            # Build the row from subdf
            row_data: Dict[str, Optional[float]] = subdf.slice(j_col, 1).to_dicts()[0]
            row_data["stable_id"] = sid
            stable_rows.append(row_data)

        # Handle unmatched stable IDs => insert a blank row
        unmatched_sids: set[int] = set(stable_id_list) - matched_sids
        for sid in unmatched_sids:
            # Produce exactly 1 row for this stable ID with 'None' for columns
            blank_row: Dict[str, Optional[float]] = {col: None for col in all_columns}
            blank_row["frame_id"] = f
            blank_row["stable_id"] = sid

            # Carry forward last known positions:
            old_pos = stable_positions[sid]
            if old_pos is not None:
                blank_row["x"] = old_pos[0]
                blank_row["y"] = old_pos[1]

            stable_rows.append(blank_row)

    # Build final dataframe from the list of dicts
    df_out: pl.DataFrame = pl.DataFrame(stable_rows)
    df_out = df_out.sort(["frame_id", "stable_id"])
    return df_out


def global_analysis(df: pl.DataFrame, output_dir: Path, file_stem: str) -> None:
    """
    Perform global analysis on the DataFrame and save the results.

    Args:
        df (pl.DataFrame): The DataFrame containing bounding box data.
        output_dir (Path): Directory to save the analysis outputs.
        file_stem (str): Stem of the input file name for output file naming.

    Returns:
        None
    """
    click.echo("\n--- Global Speed Summary ---")
    df = df.filter(pl.col("speed").is_not_null())
    global_speed_stats = df["speed"].describe()
    click.echo(global_speed_stats)
    global_speed_stats.write_csv(output_dir / f"{file_stem}_glob_speed_stats.csv")

    # normalise the histogram by total number of rows
    num_rows = len(df)
    weights = np.ones(num_rows) / num_rows

    # Global speed histogram (normalised)
    plt.hist(df["speed"], bins=50, weights=weights, alpha=0.7)
    plt.margins(x=0)
    plt.title("Global Speed Distribution (Normalised)")
    plt.xlabel("Speed")
    
    plt.ylabel("Fraction of Rows")
    outpath = output_dir / f"{file_stem}_glob_speed_hist.png"
    plt.savefig(outpath)
    plt.close()
    click.echo(f"Saved global speed histogram to {outpath}")

    click.echo("\n--- Object-Level Speed Summaries ---")
    obj_speed_stats = df.group_by("stable_id").agg(
        [
            pl.col("speed").min().alias("min"),
            pl.col("speed").quantile(0.25).alias("25%"),
            pl.col("speed").median().alias("50%"),
            pl.col("speed").quantile(0.75).alias("75%"),
            pl.col("speed").max().alias("max"),
            pl.col("speed").mean().alias("mean"),
            pl.col("speed").std().alias("std"),
            pl.col("speed").count().alias("count"),
        ]
    )
    click.echo(obj_speed_stats)
    obj_speed_stats.write_csv(output_dir / f"{file_stem}_obj_speed_stats.csv")
    
    plt.figure()
    ids = df["stable_id"].unique().to_list()
    for stable_id in ids:
        group = df.filter(pl.col("stable_id") == stable_id)
        speeds = group["speed"].to_numpy()
        n = speeds.shape[0]
        weights_obj = np.ones(n) / num_rows
        plt.hist(
            speeds,
            bins=50,
            alpha=0.5,
            label=f"ID={stable_id}",
            weights=weights_obj,
        )
    plt.title("Speed Distributions by ID (Normalised)")
    plt.xlabel("Speed")
    plt.margins(x=0)
    plt.ylabel("Fraction of All Rows")
    plt.legend()
    outpath = output_dir / f"{file_stem}_per_obj_speed_hist.png"
    plt.savefig(outpath)
    plt.close()
    click.echo(f"Saved per object speed histogram to {outpath}")

    click.echo("\n--- Global Direction Summary ---")
    # Compute direction in radians and degrees
    df = df.with_columns([
        pl.arctan2(pl.col("dy"), pl.col("dx")).alias("direction_rad"),
    ])
    df = df.with_columns([
        ((pl.col("direction_rad") * (180 / np.pi) + 360) % 360).alias("direction_deg"),
    ])

    # Basic stats on direction
    direction_stats = df.select("direction_deg").describe()
    click.echo(direction_stats)

    # Global direction histogram (normalised)
    plt.hist(df["direction_deg"], bins=36, alpha=0.7, weights=weights)
    plt.title("Global Direction Distribution (Normalised)")
    plt.xlabel("Direction (degrees)")
    plt.ylabel("Fraction of Rows")
    plt.margins(x=0)
    outpath = output_dir / f"{file_stem}_glob_dir_hist.png"
    plt.savefig(outpath)
    plt.close()
    click.echo(f"Saved global direction histogram to {outpath}")

    # Direction per object (normalised)
    plt.figure()
    for stable_id in ids:
        group = df.filter(pl.col("stable_id") == stable_id)
        dirs = group["direction_deg"].to_numpy()
        n = dirs.shape[0]
        weights_obj = np.ones(n) / num_rows
        plt.hist(
            dirs,
            bins=36,
            alpha=0.5,
            label=f"ID={stable_id}",
            weights=weights_obj,
        )
    plt.title("Direction Distributions by ID (Normalised)")
    plt.xlabel("Direction (degrees)")
    plt.ylabel("Fraction of Rows")
    plt.margins(x=0)
    plt.legend()
    outpath = output_dir / f"{file_stem}_per_obj_dir_hist.png"
    plt.savefig(outpath)
    plt.close()
    click.echo(f"Saved per object direction histogram to {outpath}")

@click.command()
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the input video file.",
)
@click.option(
    "--output",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to store output CSV files.",
)
def main(input_file: Path, output_dir: Path) -> None:
    """
    Video processing script that creates CSV files with object tracking information.

    Args:
        input_file (Path): Path to the input video file.
        output_dir (Path): Directory to store output CSV files.

    Returns:
        None
    """
    click.echo(f"Input video file: {input_file}")
    click.echo(f"Output directory: {output_dir.absolute()}")

    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("Running YOLO tracking...")
    output_csv_1 = output_dir / f"{input_file.stem}_{CSV1_NAME}"
    df = save_bboxes_to_file(
        MODEL_PATH, input_file, output_csv_1, CONF_THRESHOLD, XYWH, TRACK
    )
    click.echo(f"Output raw CSV file to {output_csv_1}")

    click.echo("Extracting flow info...")
    output_csv_2 = output_dir / f"{input_file.stem}_{CSV2_NAME}"
    df = extract_flow_info(df, FILTER_LABEL)
    df.write_csv(output_csv_2)
    click.echo(f"Saved velocity CSV to {output_csv_2}")

    click.echo("Fixing IDs...")
    output_csv_3 = output_dir / f"{input_file.stem}_{CSV3_NAME}"
    df = fix_ids(df)
    df.write_csv(output_csv_3)
    click.echo(f"Saved fixed IDs CSV to {output_csv_3}")

    click.echo("Global analysis")
    global_analysis(df, output_dir, input_file.stem)
    click.echo("Done!")


if __name__ == "__main__":
    main()

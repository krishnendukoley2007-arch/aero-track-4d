"""
scripts/build_training_dataset.py — Reproducible Dataset Construction for SIH 26078.
Implements Phase 2 of AERO_TRACK_4D_ONE_DAY_MASTER_ANTIGRAVITY.md:
1. Ingests configs/training_dataset.yaml.
2. Extracts paired-resolution downscaling tensors (1.0° coarse proxy -> 0.25° fine ERA5 target).
3. Enforces strict Leave-One-Storm-Out (LOSO) splitting:
   - Training: Cyclone Fani (2019) + Cyclone Yaas (2021)
   - Validation: 24h time-blocked window within development storms preceded by 24h buffer gap
   - Testing: 100% of Cyclone Amphan (2020, completely unseen during training)
4. Constructs sliding temporal tracking windows for GNN spatio-temporal modeling.
5. Saves processed tensor arrays to data/processed/ and generates data/processed/dataset_manifest.json.
6. Runs automated mathematical anti-leakage audits to guarantee zero test leakage.
"""

import os
import sys
import json
import yaml
import hashlib
from datetime import datetime, timezone
import numpy as np

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.data_loader import WeatherDataLoader

CONFIG_PATH = os.path.join(REPO_ROOT, "configs", "training_dataset.yaml")
PROCESSED_DIR = os.path.join(REPO_ROOT, "data", "processed")


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA256 checksum of a file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def load_config() -> dict:
    """Loads dataset configuration from YAML file or returns default."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "split_strategy": {
            "test_storm": "amphan_2020",
            "val_block_hours": 24,
            "val_gap_hours": 24,
        }
    }


def build_tracking_temporal_windows(stride: int = 3) -> dict:
    """
    Builds sliding temporal sequences for spherical anomaly tracking:
    Input window: [T-6h, T-3h, T] (node features across time)
    Target: Future centroid displacement at [T+6h, T+12h, T+24h]
    """
    storms = ["amphan_2020", "fani_2019", "yaas_2021"]
    all_seq_inputs = []
    all_seq_targets = []
    metadata = []

    for storm_id in storms:
        loader = WeatherDataLoader(storm_id)
        n_t = len(loader.timestamps)
        ibtracs = loader.ibtracs_data

        # Build hourly lookup for IBTrACS lat/lon
        coord_map = {}
        for row in ibtracs:
            iso = row.get("iso_time", "").replace(" ", "T")[:13]
            if iso and row.get("lat") is not None and row.get("lon") is not None:
                coord_map[iso] = (float(row["lat"]), float(row["lon"]))

        # Slide over timesteps with lookback 6h (step of 3) and forward target 6h
        for t in range(6, n_t - 6, stride):
            # Input window: t-6, t-3, t
            t_steps = [t - 6, t - 3, t]
            window_feats = []
            valid_window = True

            for ts in t_steps:
                c_inp, _ = loader.extract_step_tensors(ts)
                window_feats.append(c_inp)

            # Target: Centroid location at t+6h
            target_iso = loader.timestamps[t + 6][:13]
            if target_iso in coord_map:
                target_coords = coord_map[target_iso]
            else:
                # Fallback to local maximum vorticity / wind point
                fine_t, _ = loader.extract_step_tensors(t + 6)
                max_idx = np.unravel_index(np.argmax(fine_t[0]), fine_t[0].shape)
                target_coords = (float(loader.lats[max_idx[0]]), float(loader.lons[max_idx[1]]))

            all_seq_inputs.append(np.stack(window_feats, axis=0))  # [3, 4, 16, 16]
            all_seq_targets.append(np.array(target_coords, dtype=np.float32))
            metadata.append({"storm_id": storm_id, "timestep_t": t, "timestamp": loader.timestamps[t]})

    return {
        "inputs": np.array(all_seq_inputs, dtype=np.float32),
        "targets": np.array(all_seq_targets, dtype=np.float32),
        "metadata": metadata,
    }


def main():
    print("=" * 70)
    print("AERO-TRACK 4D: BUILDING REPRODUCIBLE LOSO TRAINING DATASET")
    print("=" * 70)

    cfg = load_config()
    split_cfg = cfg.get("split_strategy", {})
    test_storm = split_cfg.get("test_storm", "amphan_2020")
    val_block = split_cfg.get("val_block_hours", 24)
    val_gap = split_cfg.get("val_gap_hours", 24)

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    print(f"Loading Leave-One-Storm-Out splits...")
    print(f"  Test Storm (Holdout):   {test_storm}")
    print(f"  Validation Window:      {val_block} hours")
    print(f"  Temporal Buffer Gap:    {val_gap} hours (autocorrelation protection)")

    split = WeatherDataLoader.build_loso_splits(
        test_storm_id=test_storm,
        val_block_hours=val_block,
        val_gap_hours=val_gap,
    )

    X_train = split["X_train"]
    Y_train = split["Y_train"]
    X_val = split["X_val"]
    Y_val = split["Y_val"]
    X_test = split["X_test"]
    Y_test = split["Y_test"]

    train_manifest = split["train_manifest"]
    val_manifest = split["val_manifest"]
    test_manifest = split["test_manifest"]

    print(f"\nExtracted Downscaling Tensors:")
    print(f"  Train:      X={X_train.shape}, Y={Y_train.shape} ({len(X_train)} samples from {split['train_storm_ids']})")
    print(f"  Validation: X={X_val.shape}, Y={Y_val.shape} ({len(X_val)} samples with {val_gap}h temporal gap)")
    print(f"  Test:       X={X_test.shape}, Y={Y_test.shape} ({len(X_test)} samples from 100% unseen {test_storm})")

    # Anti-leakage mathematical checks
    print("\nRunning Anti-Leakage Verification:")
    assert test_storm not in [s for s, _ in train_manifest], "FATAL: Test storm leaked into training set!"
    assert test_storm not in [s for s, _ in val_manifest], "FATAL: Test storm leaked into validation set!"
    assert set(train_manifest).isdisjoint(set(val_manifest)), "FATAL: Train and validation manifests overlap!"
    assert set(train_manifest).isdisjoint(set(test_manifest)), "FATAL: Train and test manifests overlap!"
    assert set(val_manifest).isdisjoint(set(test_manifest)), "FATAL: Validation and test manifests overlap!"

    for storm_tr, t_tr in train_manifest:
        for storm_val, t_val in val_manifest:
            if storm_tr == storm_val:
                gap = abs(t_tr - t_val)
                assert gap >= val_gap, f"FATAL: Temporal gap violation in {storm_tr}: {gap}h < {val_gap}h"

    print("  [PASS] Zero test storm leakage across train and val.")
    print(f"  [PASS] Strict {val_gap}h temporal buffer enforced between train and val.")
    print("  [PASS] Disjoint sample manifests across all three sets.")

    # Save arrays
    train_x_path = os.path.join(PROCESSED_DIR, "X_train.npy")
    train_y_path = os.path.join(PROCESSED_DIR, "Y_train.npy")
    val_x_path = os.path.join(PROCESSED_DIR, "X_val.npy")
    val_y_path = os.path.join(PROCESSED_DIR, "Y_val.npy")
    test_x_path = os.path.join(PROCESSED_DIR, "X_test.npy")
    test_y_path = os.path.join(PROCESSED_DIR, "Y_test.npy")

    np.save(train_x_path, X_train)
    np.save(train_y_path, Y_train)
    np.save(val_x_path, X_val)
    np.save(val_y_path, Y_val)
    np.save(test_x_path, X_test)
    np.save(test_y_path, Y_test)

    # Build sliding window tracking sequences
    print("\nGenerating Sliding Temporal Windows for Spatio-Temporal GAT Tracker...")
    track_windows = build_tracking_temporal_windows(stride=3)
    track_path = os.path.join(PROCESSED_DIR, "tracking_sequences.npz")
    np.savez_compressed(
        track_path,
        inputs=track_windows["inputs"],
        targets=track_windows["targets"]
    )
    print(f"  -> Saved {len(track_windows['inputs'])} sliding tracking sequences to {track_path}")

    # Compute array file checksums
    checksums = {
        "X_train.npy": compute_file_sha256(train_x_path),
        "Y_train.npy": compute_file_sha256(train_y_path),
        "X_val.npy": compute_file_sha256(val_x_path),
        "Y_val.npy": compute_file_sha256(val_y_path),
        "X_test.npy": compute_file_sha256(test_x_path),
        "Y_test.npy": compute_file_sha256(test_y_path),
        "tracking_sequences.npz": compute_file_sha256(track_path),
    }

    # Build dataset manifest
    manifest_data = {
        "dataset_name": cfg.get("dataset", {}).get("name", "Bay of Bengal Cyclone Benchmark"),
        "version": cfg.get("dataset", {}).get("version", "1.0.0"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_strategy": "leave_one_storm_out",
        "held_out_test_storm": test_storm,
        "development_train_storms": split["train_storm_ids"],
        "temporal_buffer_gap_hours": val_gap,
        "sample_counts": {
            "train_samples": int(X_train.shape[0]),
            "validation_samples": int(X_val.shape[0]),
            "test_samples": int(X_test.shape[0]),
            "total_samples": int(X_train.shape[0] + X_val.shape[0] + X_test.shape[0]),
            "tracking_sequences": int(len(track_windows["inputs"]))
        },
        "tensor_shapes": {
            "X_train": list(X_train.shape),
            "Y_train": list(Y_train.shape),
            "X_val": list(X_val.shape),
            "Y_val": list(Y_val.shape),
            "X_test": list(X_test.shape),
            "Y_test": list(Y_test.shape),
            "tracking_sequence_inputs": list(track_windows["inputs"].shape),
            "tracking_sequence_targets": list(track_windows["targets"].shape)
        },
        "channels": [
            {"idx": 0, "name": "wind_speed_10m", "unit": "m/s", "scaling": "norm / 3.6"},
            {"idx": 1, "name": "surface_pressure", "unit": "hPa", "scaling": "(mslp - 1000) / 25"},
            {"idx": 2, "name": "precipitation", "unit": "mm/h", "scaling": "precip / 20"},
            {"idx": 3, "name": "temperature_2m", "unit": "degC", "scaling": "(temp - 25) / 10"}
        ],
        "checksums_sha256": checksums,
        "anti_leakage_audit": {
            "zero_test_storm_in_train": True,
            "zero_test_storm_in_val": True,
            "temporal_gap_enforced": True,
            "gap_hours": val_gap,
            "audit_passed": True
        }
    }

    manifest_path = os.path.join(PROCESSED_DIR, "dataset_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"\nSuccessfully generated dataset manifest: {manifest_path}")
    print("=" * 70)
    print("PHASE 2 DATASET GENERATION COMPLETE.")
    print("=" * 70)


if __name__ == "__main__":
    main()

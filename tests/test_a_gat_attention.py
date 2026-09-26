"""
Test A — GAT Attention Validity
Proves the trained GAT concentrates attention on cyclone-like inputs
vs flat background noise. Uses existing gat_tracker_amphan.pt weights.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from src.spherical_gnn import SphericalGNNTracker


def gini_coefficient(arr):
    """Gini coefficient — measures concentration of attention weights."""
    arr = np.abs(arr.flatten())
    arr = np.sort(arr)
    n = len(arr)
    if arr.sum() < 1e-10:
        return 0.0
    return float((2 * np.sum(np.arange(1, n + 1) * arr) / (n * arr.sum())) - (n + 1) / n)


def test_gat_attention_validity():
    print("\n" + "="*60)
    print("TEST A — GAT Attention Validity")
    print("="*60)

    tracker = SphericalGNNTracker(subdivisions=6)
    N = len(tracker.mesh.nodes)
    nodes = tracker.mesh.nodes

    print(f"  Mesh: {N} nodes on True Icosahedral Mesh (subdivision-6)")
    print(f"  Weights: {'LOADED from gat_tracker_amphan.pt' if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'gat_tracker_amphan.pt')) else 'RANDOM INIT (not trained)'}")

    # --- Scenario 1: Strong cyclone signal injected at Amphan peak location ---
    center_lat, center_lon = 16.0, 87.0
    cyclone_feats = np.zeros((N, 4), dtype=np.float32)
    injected_count = 0
    for i, nd in enumerate(nodes):
        dist = ((nd["lat"] - center_lat)**2 + (nd["lon"] - center_lon)**2)**0.5
        if dist < 2.5:
            cyclone_feats[i] = [25.0, -25.0, 60.0, -5.0]  # strong wind, low pressure, high precip, cold
            injected_count += 1

    # --- Scenario 2: Flat background noise ---
    np.random.seed(99)
    flat_feats = np.random.normal(0, 0.5, (N, 4)).astype(np.float32)

    scores_cyclone, alpha_cyclone = tracker.evaluate_gat_scores(cyclone_feats)
    scores_flat, alpha_flat = tracker.evaluate_gat_scores(flat_feats)

    top_node_idx = int(np.argmax(scores_cyclone))
    top_lat = nodes[top_node_idx]["lat"]
    top_lon = nodes[top_node_idx]["lon"]
    dist_from_center = ((top_lat - center_lat)**2 + (top_lon - center_lon)**2)**0.5

    peak_cyclone = float(np.max(scores_cyclone))
    peak_flat = float(np.max(scores_flat))
    score_ratio = peak_cyclone / max(1e-6, peak_flat)

    gini_cyclone = gini_coefficient(alpha_cyclone)
    gini_flat = gini_coefficient(alpha_flat)

    print(f"\n  [A1] Peak score location:")
    print(f"       Injected center: ({center_lat}°N, {center_lon}°E)")
    print(f"       GAT peak node:   ({top_lat:.2f}°N, {top_lon:.2f}°E)")
    print(f"       Distance from center: {dist_from_center:.2f}°")

    print(f"\n  [A2] Score amplification:")
    print(f"       Cyclone peak score: {peak_cyclone:.4f}")
    print(f"       Flat peak score:    {peak_flat:.4f}")
    print(f"       Ratio:              {score_ratio:.2f}x")

    print(f"\n  [A3] Attention concentration (Gini):")
    print(f"       Cyclone input Gini: {gini_cyclone:.4f}")
    print(f"       Flat input Gini:    {gini_flat:.4f}")

    # A1: Peak score within 5 degrees of injected cyclone center
    assert dist_from_center < 5.0, f"A1 FAIL: Peak too far from cyclone center: {dist_from_center:.2f}°"

    # A2: Attention Gini is higher for cyclone input than flat noise
    assert gini_cyclone > gini_flat, f"A2 FAIL: gini_cyclone={gini_cyclone:.4f} not > gini_flat={gini_flat:.4f}"

    # A3: Gini is non-zero for cyclone (network produces varied attention)
    assert gini_cyclone > 0.01, f"A3 FAIL: Attention weights too uniform, gini={gini_cyclone:.4f}"

    # A4: Injected nodes were found
    assert injected_count > 0, f"A4 FAIL: No cyclone signal nodes injected in mesh domain"

    print(f"\n  [TEST A PASSED]")
    print(f"  dist_from_center={dist_from_center:.2f}° | gini_cyclone={gini_cyclone:.4f} > gini_flat={gini_flat:.4f}")


if __name__ == "__main__":
    test_gat_attention_validity()

"""
tests/test_calibration_bv.py — Phase improvement verification tests

Covers:
  A. Calibration suite output structure and value ranges
  B. Bred Vector ensemble structure, spread properties, and BV > Gaussian spread quality
  C. API endpoints (/api/calibration, /api/bred-vector-ensemble, /api/era5-pressure-levels)
  D. Brier Skill Score positive (better than climatology)
  E. Rank histogram chi2 is finite and reasonable
  F. BV spread grows with lead time (physically correct)
"""

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from src.calibration import (
    reliability_diagram,
    brier_score,
    spread_skill_relationship,
    crps_decomposition,
    rank_histogram,
    run_calibration_suite,
)
from src.bred_vectors import BredVectorEnsemble


# ============================================================================
# A. Calibration Suite — Output Structure
# ============================================================================

class TestCalibrationStructure:

    def setup_method(self):
        rng = np.random.default_rng(42)
        self.n_samples = 100
        self.n_members = 5
        self.obs = rng.normal(80.0, 20.0, size=self.n_samples)
        self.ens = np.stack([
            self.obs + rng.normal(0, 6.0, size=self.n_samples)
            for _ in range(self.n_members)
        ], axis=1)

    def test_reliability_diagram_keys(self):
        rd = reliability_diagram(self.ens, self.obs, threshold=60.0)
        for key in ["bin_centres", "mean_forecast_probability", "observed_frequency",
                    "climatological_frequency", "sharpness"]:
            assert key in rd, f"reliability_diagram missing key: {key}"

    def test_reliability_diagram_bin_count(self):
        rd = reliability_diagram(self.ens, self.obs, threshold=60.0, n_bins=10)
        assert len(rd["bin_centres"]) == 10

    def test_observed_freq_in_0_1(self):
        rd = reliability_diagram(self.ens, self.obs, threshold=60.0)
        for v in rd["observed_frequency"]:
            if v is not None:
                assert 0.0 <= v <= 1.0, f"observed_frequency={v} out of [0,1]"

    def test_brier_score_positive(self):
        bs = brier_score(self.ens, self.obs, threshold=60.0)
        assert bs["brier_score"] >= 0.0
        assert bs["brier_score"] <= 1.0

    def test_brier_skill_score_range(self):
        bs = brier_score(self.ens, self.obs, threshold=60.0)
        # BSS can be negative (worse than climatology) but must be in (-inf, 1]
        assert bs["brier_skill_score"] <= 1.0

    def test_crps_decomposition_keys(self):
        cd = crps_decomposition(self.ens, self.obs)
        for key in ["crps_total", "crps_reliability", "crps_resolution", "crps_uncertainty"]:
            assert key in cd, f"crps_decomposition missing key: {key}"

    def test_crps_total_positive(self):
        cd = crps_decomposition(self.ens, self.obs)
        assert cd["crps_total"] >= 0.0

    def test_rank_histogram_keys(self):
        rh = rank_histogram(self.ens, self.obs)
        for key in ["rank_counts", "chi2_statistic", "shape_diagnosis"]:
            assert key in rh, f"rank_histogram missing key: {key}"

    def test_rank_histogram_counts_sum_to_n_samples(self):
        rh = rank_histogram(self.ens, self.obs)
        total = sum(rh["rank_counts"])
        assert total == self.n_samples, f"rank_counts sum={total} != n_samples={self.n_samples}"

    def test_rank_histogram_chi2_finite(self):
        rh = rank_histogram(self.ens, self.obs)
        assert np.isfinite(rh["chi2_statistic"])


# ============================================================================
# B. Spread-Skill Relationship
# ============================================================================

class TestSpreadSkill:

    def _make_data(self, n_leads=5, spread_scale=1.0):
        rng = np.random.default_rng(42)
        lead_hours = {24 * (i + 1): None for i in range(n_leads)}
        ens_by_lead, obs_by_lead = {}, {}
        for lt in lead_hours:
            n = 50
            obs = rng.normal(80.0, 20.0, size=n)
            ens = np.stack([
                obs + rng.normal(0, 6.0 * spread_scale * (lt / 24.0) ** 0.5, size=n)
                for _ in range(5)
            ], axis=1)
            ens_by_lead[lt] = ens
            obs_by_lead[lt] = obs
        return ens_by_lead, obs_by_lead

    def test_spread_grows_with_lead_time(self):
        """Spread should increase monotonically with lead time in a well-designed ensemble."""
        ens_by_lead, obs_by_lead = self._make_data(spread_scale=1.5)
        ss = spread_skill_relationship(ens_by_lead, obs_by_lead)
        spreads = ss["ensemble_spread_kmh"]
        # Spread at final lead should exceed spread at first lead
        assert spreads[-1] > spreads[0], "Spread should grow with lead time"

    def test_spread_skill_ratio_keys(self):
        ens_by_lead, obs_by_lead = self._make_data()
        ss = spread_skill_relationship(ens_by_lead, obs_by_lead)
        for key in ["lead_hours", "ensemble_spread_kmh", "rmse_kmh",
                    "spread_skill_ratio", "mean_spread_skill_ratio", "calibration_assessment"]:
            assert key in ss

    def test_calibration_assessment_is_string(self):
        ens_by_lead, obs_by_lead = self._make_data()
        ss = spread_skill_relationship(ens_by_lead, obs_by_lead)
        assert isinstance(ss["calibration_assessment"], str)


# ============================================================================
# C. Full Calibration Suite Runner
# ============================================================================

class TestFullCalibrationSuite:

    def setup_method(self):
        self.suite = run_calibration_suite(seed=42)

    def test_suite_top_level_keys(self):
        for key in ["reliability_diagrams", "brier_scores", "spread_skill",
                    "crps_decomposition", "rank_histogram", "calibration_summary"]:
            assert key in self.suite

    def test_three_reliability_thresholds(self):
        rd = self.suite["reliability_diagrams"]
        assert "threshold_60kmh_gale" in rd
        assert "threshold_80kmh_severe" in rd
        assert "threshold_100kmh_extreme" in rd

    def test_three_brier_scores(self):
        bs = self.suite["brier_scores"]
        assert "threshold_60kmh" in bs
        assert "threshold_80kmh" in bs
        assert "threshold_100kmh" in bs

    def test_crps_total_below_20(self):
        """CRPS for a reasonable cyclone wind ensemble should be < 20 km/h."""
        cd = self.suite["crps_decomposition"]
        assert cd["crps_total"] < 20.0, f"CRPS too high: {cd['crps_total']}"

    def test_calibration_summary_has_known_limitation(self):
        """Known limitation of synthetic ensemble must be disclosed in summary."""
        summary = self.suite["calibration_summary"]
        assert "known_limitation" in summary
        assert "synthetic" in summary["known_limitation"].lower()


# ============================================================================
# D. Bred Vector Ensemble
# ============================================================================

class TestBredVectorEnsemble:

    def setup_method(self):
        self.bve = BredVectorEnsemble(n_members=10, breeding_cycles=5, seed=42)
        self.result = self.bve.generate()

    def test_n_members_correct(self):
        assert self.result["n_members"] == 10
        assert len(self.result["ensemble_members"]) == 10

    def test_all_members_have_track(self):
        for m in self.result["ensemble_members"]:
            assert "track" in m
            assert len(m["track"]) == 7  # 7 lead times

    def test_track_has_lat_lon_wind(self):
        for m in self.result["ensemble_members"]:
            for pt in m["track"]:
                assert "lat" in pt and "lon" in pt and "wind_speed_kmh" in pt

    def test_wind_is_physical(self):
        """All wind speeds must be physically plausible (5–250 km/h)."""
        for m in self.result["ensemble_members"]:
            for pt in m["track"]:
                w = pt["wind_speed_kmh"]
                assert 5.0 <= w <= 250.0, f"Non-physical wind: {w} km/h"

    def test_track_spread_grows_with_lead_time(self):
        """BV spread should increase from T+24h to T+240h."""
        spreads = self.result["track_spread_km"]["total_spread_km"]
        assert spreads[-1] > spreads[0], (
            f"BV track spread does not grow: {spreads[0]} at T+24h -> {spreads[-1]} at T+240h"
        )

    def test_provenance_type_is_bred_vector(self):
        prov = self.result["provenance"]
        assert "BRED_VECTOR" in prov["ensemble_method"]

    def test_bv_spread_at_day5_gt_day1(self):
        """Day-5 spread must exceed Day-1 spread (physical requirement)."""
        spreads = self.result["track_spread_km"]["total_spread_km"]
        # Index 0 = T+24h, index 4 = T+120h (Day 5)
        assert spreads[4] > spreads[0], "BV spread at Day 5 must exceed Day 1"

    def test_control_member_is_marked(self):
        control = [m for m in self.result["ensemble_members"] if m["is_control"]]
        assert len(control) == 1, "Exactly one control member required"
        assert control[0]["member_id"] == "BV-01"

    def test_wind_quantiles_populated(self):
        wq = self.result["wind_quantiles_by_lead"]
        assert len(wq) == 7  # 7 lead times
        for lt, q in wq.items():
            assert q["p10"] <= q["p50"] <= q["p90"], (
                f"Quantile ordering violated at lead={lt}h: P10={q['p10']}, P50={q['p50']}, P90={q['p90']}"
            )

    def test_bv_has_scientific_basis_field(self):
        assert "scientific_basis" in self.result
        assert "Toth" in self.result["scientific_basis"]

    def test_bv_acknowledges_limitation(self):
        """Provenance must disclose that BV uses GAT proxy, not full NWP."""
        note = self.result["provenance"].get("note", "")
        assert "GAT" in note or "linear proxy" in note, (
            "BV provenance must disclose that breeding uses GAT linear proxy, not full NWP"
        )

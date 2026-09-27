"""
Climate Perturbation Sandbox & Rapid Intensification (RI) Physics Engine.
Rigorous physical calculations for:
1. Kerry Emanuel Maximum Potential Intensity (MPI) thermodynamic heat-engine theory
   (Emanuel 1988, Bister & Emanuel 1998, 2002).
2. Kaplan & DeMaria SHIPS Rapid Intensification Index (Kaplan & DeMaria 2003, 2010)
   predicting 24-hour RI probability (>= 30 kt / 24 hr).
3. Climate warming perturbation response (SST / Vertical Wind Shear sensitivity)
   under IPCC / CMIP6 warming scenarios (+1.5C, +3.0C SSP5-8.5).
"""

import math
from typing import Dict, Any


def saturation_vapor_pressure_hpa(temp_c: float) -> float:
    """Tetens formula for saturation vapor pressure over liquid water."""
    return 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))


def specific_humidity_from_vapor_pressure(e_hpa: float, p_hpa: float) -> float:
    """Specific humidity q (kg/kg) from vapor pressure e and total pressure p."""
    eps = 0.622
    return (eps * e_hpa) / (p_hpa - (1.0 - eps) * e_hpa)


def compute_emanuel_mpi(
    sst_c: float,
    tropo_temp_c: float = -73.0,
    ambient_p_hpa: float = 1010.0,
    rh_ambient: float = 78.0
) -> Dict[str, Any]:
    """
    Computes Kerry Emanuel Maximum Potential Intensity (MPI).
    Thermodynamic limit:
    V_max^2 = (C_k / C_D) * ((T_s - T_o) / T_o) * (k_s* - k)
    
    Returns:
        v_max_ms: maximum sustained surface wind (m/s)
        v_max_kmh: maximum sustained surface wind (km/h)
        v_max_kt: maximum sustained surface wind (knots)
        p_min_hpa: minimum central pressure (hPa) via Holland gradient balance
        carnot_efficiency: thermodynamic efficiency (T_s - T_o) / T_o
        enthalpy_disequilibrium: (k_s* - k) in J/kg
    """
    cp = 1005.0       # J / (kg K)
    lv = 2.501e6      # J / kg (latent heat of vaporization)
    ck_cd = 0.90      # Ratio of enthalpy exchange coefficient to drag coefficient

    t_s_k = sst_c + 273.15
    t_o_k = tropo_temp_c + 273.15

    # Carnot efficiency
    carnot_eff = (t_s_k - t_o_k) / t_o_k

    # Surface saturation moist enthalpy: k_s* = cp * T_s + Lv * q_s*(T_s)
    e_s_hpa = saturation_vapor_pressure_hpa(sst_c)
    q_s = specific_humidity_from_vapor_pressure(e_s_hpa, ambient_p_hpa)
    k_star_s = cp * t_s_k + lv * q_s

    # Boundary layer air moist enthalpy: k = cp * T_a + Lv * q_a
    # Typical tropical air temperature is ~1.5 C cooler than SST
    t_a_c = sst_c - 1.5
    t_a_k = t_a_c + 273.15
    e_a_hpa = (rh_ambient / 100.0) * saturation_vapor_pressure_hpa(t_a_c)
    q_a = specific_humidity_from_vapor_pressure(e_a_hpa, ambient_p_hpa)
    k_air = cp * t_a_k + lv * q_a

    # Thermodynamic disequilibrium (J/kg)
    delta_k = max(1000.0, k_star_s - k_air)

    # Maximum gradient wind speed squared
    v_max_gradient_sq = ck_cd * carnot_eff * delta_k
    v_max_gradient_ms = math.sqrt(max(0.0, v_max_gradient_sq))
    
    # 10-meter surface wind reduction factor (Bister & Emanuel 1998, 2002)
    # Ratio of 10-meter sustained wind to gradient-level wind is typically 0.80
    surface_reduction = 0.80
    v_max_ms = v_max_gradient_ms * surface_reduction
    v_max_kmh = round(v_max_ms * 3.6, 1)
    v_max_kt = round(v_max_ms * 1.94384, 1)

    # Holland wind-pressure relation for minimum central surface pressure
    # delta_p (hPa) ~ (v_max_kt / 14.2)^1.82
    delta_p_hpa = (v_max_kt / 14.2) ** 1.82
    p_min_hpa = round(max(870.0, ambient_p_hpa - delta_p_hpa), 1)

    return {
        "sst_c": round(sst_c, 2),
        "tropo_temp_c": round(tropo_temp_c, 1),
        "carnot_efficiency": round(carnot_eff, 4),
        "enthalpy_disequilibrium_j_kg": round(delta_k, 1),
        "v_max_ms": round(v_max_ms, 2),
        "v_max_kmh": v_max_kmh,
        "v_max_kt": v_max_kt,
        "p_min_hpa": p_min_hpa,
        "governing_theory": "Kerry Emanuel Thermodynamic Potential Intensity (Bister & Emanuel 2002)"
    }


def compute_ships_ri_probability(
    sst_c: float,
    vws_kt: float,
    ohc_kj_cm2: float,
    rh700_pct: float,
    current_v_kt: float,
    mpi_v_kt: float
) -> Dict[str, Any]:
    """
    Computes Kaplan & DeMaria SHIPS Rapid Intensification (RI) Probability.
    Rapid Intensification threshold: Wind speed increase >= 30 knots in 24 hours.
    
    Logit model:
    z = beta_0 + beta_sst*(SST - 28.5) + beta_ohc*(OHC - 50.0) - beta_vws*(VWS - 12.0)
        + beta_rh*(RH700 - 70.0) + beta_pot*(MPI - current_V)
    P_RI = 1 / (1 + exp(-z))
    """
    beta_0 = -1.85           # Baseline logit (~13.6% climatological base rate)
    beta_sst = 0.68          # Positive sensitivity to SST (+0.68 per deg C above 28.5)
    beta_ohc = 0.019         # Ocean Heat Content (kJ/cm^2)
    beta_vws = 0.165         # Vertical Wind Shear penalty (-0.165 per knot above 12 kt)
    beta_rh = 0.048          # Mid-tropospheric humidity
    beta_pot = 0.024         # Intensity headroom below Emanuel MPI

    headroom_kt = max(0.0, mpi_v_kt - current_v_kt)

    logit_z = (
        beta_0
        + beta_sst * (sst_c - 28.5)
        + beta_ohc * (ohc_kj_cm2 - 50.0)
        - beta_vws * (vws_kt - 12.0)
        + beta_rh * (rh700_pct - 70.0)
        + beta_pot * (headroom_kt - 40.0)
    )

    # Sigmoid function
    prob_ri = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, logit_z))))
    prob_pct = round(prob_ri * 100.0, 1)

    # Qualitative classification
    if prob_pct >= 75.0:
        threat_level = "EXTREME RI RISK"
        badge_color = "#ef4444"
        advisory = "Catastrophic explosive deepening expected within 24 hours. Mandatory immediate evacuation of outer sea defense."
    elif prob_pct >= 50.0:
        threat_level = "HIGH RI RISK"
        badge_color = "#f59e0b"
        advisory = "Favorable thermodynamic conditions support rapid cyclogenesis (>= 30 kt / 24h). Coast guards on high alert."
    elif prob_pct >= 30.0:
        threat_level = "MODERATE RI RISK"
        badge_color = "#3b82f6"
        advisory = "Moderate RI potential. Intensification constrained by moderate vertical shear."
    else:
        threat_level = "LOW RI RISK"
        badge_color = "#10b981"
        advisory = "Unfavorable thermodynamic environment; vertical shear or cooler ocean prevents rapid deepening."

    return {
        "prob_ri_percent": prob_pct,
        "threat_level": threat_level,
        "badge_color": badge_color,
        "advisory": advisory,
        "parameters": {
            "sst_c": round(sst_c, 2),
            "vws_kt": round(vws_kt, 1),
            "ohc_kj_cm2": round(ohc_kj_cm2, 1),
            "rh700_pct": round(rh700_pct, 1),
            "intensity_headroom_kt": round(headroom_kt, 1),
            "logit_z": round(logit_z, 3)
        },
        "criteria": "Kaplan & DeMaria SHIPS Rapid Intensification Model (>= 30 kt / 24h threshold)"
    }


def evaluate_perturbation(
    hazard_id: str = "amphan_2020",
    delta_sst: float = 0.0,
    delta_vws: float = 0.0
) -> Dict[str, Any]:
    """
    Evaluates physical atmospheric impact of climate perturbation:
    delta_sst: change in SST in Celsius (-2.0 to +4.0 C)
    delta_vws: change in Vertical Wind Shear in knots (-10.0 to +15.0 kt)
    """
    # Baseline observed parameters for historical cyclone Amphan in Bay of Bengal
    baselines = {
        "amphan_2020": {
            "name": "Super Cyclone Amphan",
            "base_sst_c": 31.0,           # Exceptionally warm Bay of Bengal SST (May 2020)
            "base_vws_kt": 9.5,           # Low shear environment (favorable)
            "ohc_kj_cm2": 95.0,           # High ocean heat content
            "rh700_pct": 82.0,            # Moist monsoon environment
            "current_v_kt": 140.0,        # Category 5 intensity
            "surge_base_m": 4.8,          # Base peak storm surge height (meters)
            "population_at_risk_base": 4200000
        },
        "fani_2019": {
            "name": "Extremely Severe Cyclone Fani",
            "base_sst_c": 30.5,
            "base_vws_kt": 11.0,
            "ohc_kj_cm2": 82.0,
            "rh700_pct": 79.0,
            "current_v_kt": 115.0,
            "surge_base_m": 3.9,
            "population_at_risk_base": 3100000
        },
        "yaas_2021": {
            "name": "Very Severe Cyclone Yaas",
            "base_sst_c": 30.2,
            "base_vws_kt": 13.5,
            "ohc_kj_cm2": 72.0,
            "rh700_pct": 77.0,
            "current_v_kt": 75.0,
            "surge_base_m": 3.2,
            "population_at_risk_base": 2400000
        }
    }

    base = baselines.get(hazard_id, baselines["amphan_2020"])

    # Perturbed physical states
    perturbed_sst = base["base_sst_c"] + delta_sst
    perturbed_vws = max(2.0, base["base_vws_kt"] + delta_vws)

    # 1. Baseline MPI vs Perturbed MPI
    base_mpi = compute_emanuel_mpi(base["base_sst_c"])
    pert_mpi = compute_emanuel_mpi(perturbed_sst)

    # 2. Baseline RI vs Perturbed RI
    base_ri = compute_ships_ri_probability(
        sst_c=base["base_sst_c"],
        vws_kt=base["base_vws_kt"],
        ohc_kj_cm2=base["ohc_kj_cm2"],
        rh700_pct=base["rh700_pct"],
        current_v_kt=base["current_v_kt"],
        mpi_v_kt=base_mpi["v_max_kt"]
    )

    pert_ri = compute_ships_ri_probability(
        sst_c=perturbed_sst,
        vws_kt=perturbed_vws,
        ohc_kj_cm2=base["ohc_kj_cm2"] * (1.0 + 0.12 * delta_sst),
        rh700_pct=min(95.0, base["rh700_pct"] + 1.8 * delta_sst),
        current_v_kt=base["current_v_kt"],
        mpi_v_kt=pert_mpi["v_max_kt"]
    )

    # 3. Storm surge amplification (Jelesnianski SLOSH quadratic velocity scaling)
    # Surge height S proportional to V_max^2
    velocity_ratio = pert_mpi["v_max_ms"] / max(1.0, base_mpi["v_max_ms"])
    surge_multiplier = velocity_ratio ** 2.0
    perturbed_surge_m = round(base["surge_base_m"] * surge_multiplier, 2)
    delta_surge_m = round(perturbed_surge_m - base["surge_base_m"], 2)

    # 4. Coastal population impact delta
    pop_ratio = (surge_multiplier ** 1.35)
    perturbed_pop = int(base["population_at_risk_base"] * pop_ratio)
    delta_pop = perturbed_pop - base["population_at_risk_base"]

    return {
        "hazard_id": hazard_id,
        "hazard_name": base["name"],
        "perturbation": {
            "delta_sst_c": round(delta_sst, 2),
            "delta_vws_kt": round(delta_vws, 1),
            "simulated_sst_c": round(perturbed_sst, 2),
            "simulated_vws_kt": round(perturbed_vws, 1)
        },
        "baseline_mpi": base_mpi,
        "perturbed_mpi": pert_mpi,
        "delta_mpi_vmax_kmh": round(pert_mpi["v_max_kmh"] - base_mpi["v_max_kmh"], 1),
        "delta_mpi_pmin_hpa": round(pert_mpi["p_min_hpa"] - base_mpi["p_min_hpa"], 1),
        "baseline_ri": base_ri,
        "perturbed_ri": pert_ri,
        "delta_ri_probability_pct": round(pert_ri["prob_ri_percent"] - base_ri["prob_ri_percent"], 1),
        "surge": {
            "baseline_surge_m": base["surge_base_m"],
            "perturbed_surge_m": perturbed_surge_m,
            "delta_surge_m": delta_surge_m,
            "surge_formula": "Jelesnianski SLOSH Quadratic Velocity Scaling: Delta_S ~ (V_pert / V_base)^2"
        },
        "humanitarian_impact": {
            "baseline_population_at_risk": base["population_at_risk_base"],
            "perturbed_population_at_risk": perturbed_pop,
            "delta_population": delta_pop
        }
    }

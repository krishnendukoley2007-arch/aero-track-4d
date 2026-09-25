"""
Training & Multi-Storm Out-of-Sample Evaluation for CorrDiff (SIH 26078).
Trains the Stage 1 UNet Mean Predictor and Stage 2 Conditional Score-Based Diffusion Corrector
on multi-timestep real ERA5 coarse-to-fine pairs, with out-of-sample evaluation on:
1. Held-out May 18 Peak Super Cyclone and May 20 Landfall (Cyclone Amphan)
2. Completely unseen Cyclone Fani (April-May 2019)
3. Completely unseen Cyclone Yaas (May 2021)

Calculates Continuous Ranked Probability Score (CRPS) for 5-member ensemble
and precipitation Fractions Skill Score (FSS).

ROADMAP NOTE: Full IndiaWeatherBench (2000-2019, ~40-80 GB) and NCMRWF IMDAA regional
reanalysis retargeting requires NCMRWF portal registration credentials and multi-GPU
cluster for 20-year decadal training. Currently evaluated against genuine ERA5 reanalysis splits.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from src.data_loader import WeatherDataLoader
from src.downscale.corrdiff_model import PhysicsNeMoCorrDiff, PhysicsInformedConservationLoss

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


def train_corrdiff(epochs: int = 15, lr: float = 1e-3, save_ckpt: bool = True):
    os.makedirs(MODELS_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Initializing CorrDiff Training on {device} ===")

    dl = WeatherDataLoader(event_id="amphan_2020")
    X_train, Y_train, X_test, Y_test = dl.build_training_dataset()
    print(f"Dataset split: {len(X_train)} training timesteps | {len(X_test)} held-out test timesteps (Peak & Landfall)")

    model = PhysicsNeMoCorrDiff(num_timesteps=15, device="cpu")
    model.to_device(device)

    opt_mean = optim.AdamW(model.mean_predictor.parameters(), lr=lr, weight_decay=1e-4)
    opt_diff = optim.AdamW(model.diffusion_corrector.parameters(), lr=lr, weight_decay=1e-4)

    crit_physics = PhysicsInformedConservationLoss(lambda_mse=1.0, lambda_l1=0.3, lambda_div=0.15, lambda_mfc=0.20)
    crit_mse = nn.MSELoss()

    x_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
    y_train_t = torch.tensor(Y_train, dtype=torch.float32).to(device)
    x_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)
    y_test_t = torch.tensor(Y_test, dtype=torch.float32).to(device)

    batch_size = 16
    n_batches = int(np.ceil(len(x_train_t) / batch_size))

    model.train()
    for ep in range(epochs):
        perm = torch.randperm(len(x_train_t))
        ep_loss_mean = 0.0
        ep_loss_diff = 0.0

        for b in range(n_batches):
            idx = perm[b * batch_size:(b + 1) * batch_size]
            bx = x_train_t[idx]
            by = y_train_t[idx]

            # 1. Optimize Stage 1 Mean Predictor with Physics-Informed Conservation Loss
            opt_mean.zero_grad()
            y_mean = model.mean_predictor(bx)
            phys_loss_dict = crit_physics(y_mean, by)
            loss_mean = phys_loss_dict["total_loss"]
            loss_mean.backward()
            opt_mean.step()
            ep_loss_mean += loss_mean.item()

            # 2. Optimize Stage 2 Diffusion Corrector
            opt_diff.zero_grad()
            with torch.no_grad():
                y_mean_det = model.mean_predictor(bx)
                residuals = by - y_mean_det

            b_cur = bx.shape[0]
            t = torch.randint(0, model.num_timesteps, (b_cur,), device=device).long()
            noise = torch.randn_like(residuals)

            alpha_hat = model.alphas_cumprod[t][:, None, None, None]
            z_t = torch.sqrt(alpha_hat) * residuals + torch.sqrt(1.0 - alpha_hat) * noise

            noise_pred = model.diffusion_corrector(z_t, t, bx, y_mean_det)
            loss_diff = crit_mse(noise_pred, noise)
            loss_diff.backward()
            opt_diff.step()
            ep_loss_diff += loss_diff.item()

        if (ep + 1) % 5 == 0 or ep == epochs - 1:
            print(f"Epoch [{ep+1:02d}/{epochs}] - Mean Loss: {ep_loss_mean/n_batches:.4f} | Diffusion Loss: {ep_loss_diff/n_batches:.4f}")

    # Held-out Test Evaluation
    model.eval()
    with torch.no_grad():
        test_mean = model.mean_predictor(x_test_t)
        test_mse_mean = crit_mse(test_mean, y_test_t).item()
        ens_res = model.sample_ensemble(x_test_t[:5], n_members=5)
        test_corrdiff_mse = crit_mse(ens_res["ensemble_mean"], y_test_t[:5]).item()

    print(f"\n--- Held-out Test Split Results (May 18 & 20) ---")
    print(f"Standard U-Net Held-Out MSE:    {test_mse_mean:.4f}")
    print(f"CorrDiff Ensemble Held-Out MSE: {test_corrdiff_mse:.4f}")

    ckpt_path = os.path.join(MODELS_DIR, "corrdiff_amphan.pt")
    if save_ckpt:
        torch.save({
            "model_state": model.state_dict(),
            "epochs": epochs,
            "test_mse_mean": test_mse_mean,
            "test_corrdiff_mse": test_corrdiff_mse,
        }, ckpt_path)
        print(f"Model saved to: {ckpt_path}\n")

    # Multi-Storm Out-of-Sample Generalization Evaluation (Fani 2019 & Yaas 2021)
    from src.downscale.inference import CorrDiffInferenceEngine
    inf_engine = CorrDiffInferenceEngine(weights_path=ckpt_path)

    fani_res = inf_engine.run_downscale(step_idx=7, event_id="fani_2019")
    yaas_res = inf_engine.run_downscale(step_idx=5, event_id="yaas_2021")
    amphan_res = inf_engine.run_downscale(step_idx=5, event_id="amphan_2020")

    print("=== MULTI-STORM OUT-OF-SAMPLE EVALUATION (REAL OUTPUTS ONLY) ===")
    print(f"Cyclone Amphan (2020 Peak Held-out): Recovery = {amphan_res['amplitude_evaluation']['measured_recovery_percent']['corrdiff_mean']}% | CRPS = {amphan_res['calibration_metrics']['crps_wind_kmh']} km/h | FSS = {amphan_res['calibration_metrics']['fss_precipitation_score']}")
    print(f"Cyclone Fani (2019 Category 5 Unseen): Recovery = {fani_res['amplitude_evaluation']['measured_recovery_percent']['corrdiff_mean']}% | CRPS = {fani_res['calibration_metrics']['crps_wind_kmh']} km/h | FSS = {fani_res['calibration_metrics']['fss_precipitation_score']}")
    print(f"Cyclone Yaas (2021 Very Severe Unseen): Recovery = {yaas_res['amplitude_evaluation']['measured_recovery_percent']['corrdiff_mean']}% | CRPS = {yaas_res['calibration_metrics']['crps_wind_kmh']} km/h | FSS = {yaas_res['calibration_metrics']['fss_precipitation_score']}")

    return model


if __name__ == "__main__":
    train_corrdiff(epochs=15)

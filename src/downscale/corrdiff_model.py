"""
PhysicsNeMo CorrDiff Two-Stage Architecture for Scientific Downscaling (SIH 26078).
Implements:
1. Stage 1: UNet Mean Predictor for deterministic large-scale features.
2. Stage 2: Conditional Score-Based Denoising Diffusion Corrector for stochastic peak recovery.
3. Multi-Member Diffusion Ensemble Sampling (N=5 realizations) and Spread/Uncertainty derivation.
4. Radially Averaged 2D Power Spectral Density (PSD) analysis for spectral smoothing audits.
5. Post-hoc Physical Diagnostic Conservation checks (Moisture Convergence, Divergence).
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, Tuple, Any, List


class PhysicsInformedConservationLoss(nn.Module):
    """
    Physics-Informed Conservation Loss for CorrDiff downscaling.
    Directly satisfies SIH 26078 Technical Methodology:
    "To ensure the model remains scientifically accurate, we embed fluid dynamics
    and thermodynamic conservation laws directly into the neural network's loss function.
    The model is mathematically penalized if it generates physically impossible weather
    states (e.g., severe downpours missing corresponding moisture convergence vectors)."
    """
    def __init__(self, lambda_mse: float = 1.0, lambda_l1: float = 0.3,
                 lambda_div: float = 0.15, lambda_mfc: float = 0.20, dx: float = 5000.0):
        super().__init__()
        self.lambda_mse = lambda_mse
        self.lambda_l1 = lambda_l1
        self.lambda_div = lambda_div
        self.lambda_mfc = lambda_mfc
        self.dx = dx
        self.mse = nn.MSELoss()
        self.l1 = nn.L1Loss()

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> Dict[str, torch.Tensor]:
        # pred: [B, 4, H, W] -> channels: 0: wind, 1: mslp, 2: precip, 3: temp
        loss_mse = self.mse(pred, target)
        loss_l1 = self.l1(pred, target)

        # 1. 2D Mass Divergence / Continuity Loss: div(V) -> 0
        w = pred[:, 0:1]  # normalized wind speed
        dw_dx = (w[:, :, :, 2:] - w[:, :, :, :-2]) / (2.0 * self.dx)
        dw_dy = (w[:, :, 2:, :] - w[:, :, :-2, :]) / (2.0 * self.dx)
        div_loss = torch.mean((dw_dx[:, :, 1:-1, :] + dw_dy[:, :, :, 1:-1]) ** 2)

        # 2. Thermodynamic Moisture Flux Convergence (MFC) Penalty:
        # Penalizes intense rain cells that lack boundary layer convergence
        precip = pred[:, 2:3]
        wind_conv = -(dw_dx[:, :, 1:-1, :] + dw_dy[:, :, :, 1:-1])
        precip_crop = precip[:, :, 1:-1, 1:-1]
        
        # Penalize precipitation where convergence is negative (divergent drying air)
        mfc_violation = F.relu(precip_crop - 0.2) * F.relu(-wind_conv * 1e4)
        loss_mfc = torch.mean(mfc_violation)

        total_loss = (self.lambda_mse * loss_mse + 
                      self.lambda_l1 * loss_l1 + 
                      self.lambda_div * div_loss + 
                      self.lambda_mfc * loss_mfc)

        return {
            "total_loss": total_loss,
            "loss_mse": loss_mse,
            "loss_l1": loss_l1,
            "loss_divergence": div_loss,
            "loss_moisture_convergence": loss_mfc,
        }


class SinusoidalPositionEmbeddings(nn.Module):
    """Sinusoidal embeddings for diffusion timestep t."""
    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def forward(self, time: torch.Tensor) -> torch.Tensor:
        device = time.device
        half_dim = self.dim // 2
        embeddings = math.log(10000) / (half_dim - 1)
        embeddings = torch.exp(torch.arange(half_dim, device=device) * -embeddings)
        embeddings = time[:, None] * embeddings[None, :]
        return torch.cat((embeddings.sin(), embeddings.cos()), dim=-1)


class DoubleConv(nn.Module):
    """Conv -> BatchNorm -> GELU -> Conv -> BatchNorm -> GELU"""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.GELU(),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.GELU()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class CorrDiffMeanPredictor(nn.Module):
    """
    Stage 1: UNet Mean Predictor.
    Optimized for MSE/L1 loss; naturally models the conditional mean field.
    """
    def __init__(self, in_channels: int = 4, out_channels: int = 4, base_dim: int = 32):
        super().__init__()
        self.inc = DoubleConv(in_channels, base_dim)
        self.down = nn.Sequential(nn.MaxPool2d(2), DoubleConv(base_dim, base_dim * 2))
        self.bot = DoubleConv(base_dim * 2, base_dim * 2)
        self.up = nn.ConvTranspose2d(base_dim * 2, base_dim, kernel_size=2, stride=2)
        self.out_conv = nn.Sequential(
            DoubleConv(base_dim * 2, base_dim),
            nn.Conv2d(base_dim, out_channels, kernel_size=1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(x)
        x2 = self.down(x1)
        xb = self.bot(x2)
        u = self.up(xb)
        if u.shape != x1.shape:
            u = F.interpolate(u, size=x1.shape[2:], mode="bilinear", align_corners=False)
        out = self.out_conv(torch.cat([u, x1], dim=1))
        return out


class CorrDiffDiffusionCorrector(nn.Module):
    """
    Stage 2: Conditional Score-based Diffusion Residual Corrector.
    Predicts noise epsilon to reconstruct high-frequency turbulence and peak amplitudes.
    """
    def __init__(self, in_channels: int = 4, cond_channels: int = 8, base_dim: int = 32, time_dim: int = 64):
        super().__init__()
        self.time_mlp = nn.Sequential(
            SinusoidalPositionEmbeddings(time_dim),
            nn.Linear(time_dim, time_dim),
            nn.GELU()
        )

        total_in = in_channels + cond_channels  # 4 noisy latent + 4 coarse cond + 4 mean cond = 12
        self.in_conv = DoubleConv(total_in, base_dim)
        self.t_proj = nn.Linear(time_dim, base_dim)
        
        self.down = nn.Sequential(nn.MaxPool2d(2), DoubleConv(base_dim, base_dim * 2))
        self.bot = DoubleConv(base_dim * 2, base_dim * 2)
        self.up = nn.ConvTranspose2d(base_dim * 2, base_dim, kernel_size=2, stride=2)
        self.out_conv = nn.Sequential(
            DoubleConv(base_dim * 2, base_dim),
            nn.Conv2d(base_dim, in_channels, kernel_size=1)
        )

    def forward(self, z_t: torch.Tensor, t: torch.Tensor, cond_coarse: torch.Tensor, cond_mean: torch.Tensor) -> torch.Tensor:
        t_emb = self.time_mlp(t)
        x_cat = torch.cat([z_t, cond_coarse, cond_mean], dim=1)
        
        x1 = self.in_conv(x_cat)
        x1 = x1 + self.t_proj(t_emb)[:, :, None, None]

        x2 = self.down(x1)
        xb = self.bot(x2)

        u = self.up(xb)
        if u.shape != x1.shape:
            u = F.interpolate(u, size=x1.shape[2:], mode="bilinear", align_corners=False)
        out = self.out_conv(torch.cat([u, x1], dim=1))
        return out


class PhysicsNeMoCorrDiff(nn.Module):
    """
    Two-Stage CorrDiff Pipeline with Stochastic Ensemble Realizations.
    """
    def __init__(self, num_timesteps: int = 15, device: str = "cpu"):
        super().__init__()
        self.num_timesteps = num_timesteps
        self.device = torch.device(device)

        self.mean_predictor = CorrDiffMeanPredictor()
        self.diffusion_corrector = CorrDiffDiffusionCorrector()

        # DDPM Linear Beta Schedule
        self.betas = torch.linspace(1e-4, 0.02, num_timesteps).to(self.device)
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0).to(self.device)
        self.alphas_cumprod_prev = F.pad(self.alphas_cumprod[:-1], (1, 0), value=1.0)
        self.sqrt_alphas_cumprod = torch.sqrt(self.alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - self.alphas_cumprod)
        self.posterior_variance = self.betas * (1.0 - self.alphas_cumprod_prev) / (1.0 - self.alphas_cumprod)

    def to_device(self, dev: torch.device):
        self.device = dev
        self.to(dev)
        self.betas = self.betas.to(dev)
        self.alphas = self.alphas.to(dev)
        self.alphas_cumprod = self.alphas_cumprod.to(dev)
        self.alphas_cumprod_prev = self.alphas_cumprod_prev.to(dev)
        self.sqrt_alphas_cumprod = self.sqrt_alphas_cumprod.to(dev)
        self.sqrt_one_minus_alphas_cumprod = self.sqrt_one_minus_alphas_cumprod.to(dev)
        self.posterior_variance = self.posterior_variance.to(dev)

    @torch.no_grad()
    def sample_ensemble(self, coarse_input: torch.Tensor, n_members: int = 5) -> Dict[str, Any]:
        """
        Samples N stochastic diffusion ensemble members.
        Returns:
        - stage1_mean: deterministic U-Net baseline prediction
        - ensemble_members: list of N stochastic generated realizations
        - ensemble_mean: mean across N stochastic members
        - ensemble_spread: standard deviation across members (spatial uncertainty map)
        - high_impact_scenario: 90th percentile wind realization
        """
        self.eval()
        b, c, h, w = coarse_input.shape
        coarse_input = coarse_input.to(self.device)

        # Stage 1: Deterministic Mean Prediction (Standard U-Net output)
        y_mean = self.mean_predictor(coarse_input)

        members = []
        for m in range(n_members):
            z_t = torch.randn_like(y_mean)
            step_indices = list(reversed(range(0, self.num_timesteps)))

            for t_idx in step_indices:
                t_batch = torch.full((b,), t_idx, device=self.device, dtype=torch.long)
                eps = self.diffusion_corrector(z_t, t_batch, coarse_input, y_mean)

                alpha = self.alphas[t_idx]
                alpha_cumprod = self.alphas_cumprod[t_idx]
                beta = self.betas[t_idx]

                noise = torch.randn_like(z_t) if t_idx > 0 else torch.zeros_like(z_t)
                z_t = (1.0 / torch.sqrt(alpha)) * (z_t - (beta / torch.sqrt(1.0 - alpha_cumprod)) * eps) + \
                      torch.sqrt(self.posterior_variance[t_idx]) * noise

            # Each member = deterministic mean + stochastic high-frequency correction
            y_sample = y_mean + 0.35 * z_t
            members.append(y_sample)

        members_tensor = torch.stack(members)  # [N, B, C, H, W]
        ens_mean = torch.mean(members_tensor, dim=0)
        ens_spread = torch.std(members_tensor, dim=0)
        
        # High impact scenario: Mean + 1.28 * Spread
        high_impact = ens_mean + 1.28 * ens_spread

        return {
            "stage1_mean": y_mean,
            "ensemble_members": members,
            "ensemble_mean": ens_mean,
            "ensemble_spread": ens_spread,
            "high_impact_scenario": high_impact,
        }

    @staticmethod
    def compute_power_spectrum(field_2d: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the Radially Averaged 2D Power Spectral Density (PSD) E(k) vs wavenumber k.
        A standard atmospheric diagnostic proving whether a model suffers from spectral smoothing.
        """
        h, w = field_2d.shape
        fft2 = np.fft.fft2(field_2d)
        fft_shift = np.fft.fftshift(fft2)
        psd2d = np.abs(fft_shift)**2

        y, x = np.indices((h, w))
        center = (h // 2, w // 2)
        r = np.hypot(x - center[1], y - center[0]).astype(int)

        max_k = min(center)
        k_vals = np.arange(1, max_k)
        tbin = np.bincount(r.ravel(), psd2d.ravel())
        nr = np.bincount(r.ravel())
        radial_profile = tbin[1:max_k] / np.maximum(1, nr[1:max_k])

        return k_vals, radial_profile

    @staticmethod
    def compute_physics_diagnostics(wind_speed: np.ndarray, u: np.ndarray, v: np.ndarray,
                                     mslp: np.ndarray, precip: np.ndarray, dx_km: float = 12.0) -> Dict[str, Any]:
        """
        Post-hoc Physical Diagnostic Conservation Audits:
        1. 2D Divergence: du/dx + dv/dy
        2. Moisture Flux Convergence: - div(V * q)
        3. Relative Vorticity: dv/dx - du/dy
        """
        dx = dx_km * 1000.0  # meters
        dy = dx_km * 1000.0

        dudx = np.gradient(u, dx, axis=1)
        dvdy = np.gradient(v, dy, axis=0)
        div = dudx + dvdy

        dvdx = np.gradient(v, dx, axis=1)
        dudy = np.gradient(u, dy, axis=0)
        vort = dvdx - dudy

        # Moisture convergence assuming boundary layer specific humidity ~0.02 kg/kg
        q_est = 0.02
        mfc = -(np.gradient(u * q_est, dx, axis=1) + np.gradient(v * q_est, dy, axis=0))

        # Check alignment: rain should predominantly occur in convergent areas (MFC > 0)
        pos_rain = precip > 0.5
        if np.any(pos_rain):
            alignment = float(np.mean(mfc[pos_rain] > -1e-6))
        else:
            alignment = 1.0

        div_norm = float(np.mean(np.abs(div)))
        max_vort = float(np.max(np.abs(vort)))
        diagnostic_score = round(min(100.0, max(0.0, (alignment * 0.6 + (1.0 - min(1.0, div_norm * 1e4)) * 0.4) * 100)), 1)

        return {
            "moisture_convergence_alignment": round(alignment, 3),
            "mass_divergence_norm_s-1": float(f"{div_norm:.2e}"),
            "max_vorticity_s-1": float(f"{max_vort:.2e}"),
            "diagnostic_conformity_score": diagnostic_score,
            "audit_type": "Post-Hoc Diagnostic Check (Fluid Dynamics Consistency)",
        }

    @staticmethod
    def compute_crps(ensemble_predictions: np.ndarray, observation: np.ndarray) -> float:
        """
        Computes Continuous Ranked Probability Score (CRPS) for an M-member ensemble against observation:
        CRPS(F, y) = (1/M) sum_{m=1}^M |x_m - y| - (1 / (2*M^2)) sum_{m=1}^M sum_{m'=1}^M |x_m - x_m'|
        """
        M = ensemble_predictions.shape[0]
        term1 = np.mean(np.abs(ensemble_predictions - observation[None, ...]), axis=0)
        term2 = np.zeros_like(observation)
        for m in range(M):
            for mp in range(M):
                term2 += np.abs(ensemble_predictions[m] - ensemble_predictions[mp])
        term2 /= (2.0 * M * M)
        crps_grid = term1 - term2
        return float(np.mean(crps_grid))

    @staticmethod
    def compute_fractions_skill_score(pred: np.ndarray, target: np.ndarray,
                                      threshold: float = 2.0, window_size: int = 5) -> float:
        """
        Computes precipitation Fractions Skill Score (FSS) at given exceedance threshold over spatial window:
        FSS = 1 - MSE / MSE_ref
        """
        from scipy.ndimage import uniform_filter
        b_pred = (pred >= threshold).astype(np.float32)
        b_targ = (target >= threshold).astype(np.float32)
        f_pred = uniform_filter(b_pred, size=window_size, mode='constant', cval=0.0)
        f_targ = uniform_filter(b_targ, size=window_size, mode='constant', cval=0.0)
        mse = np.mean((f_pred - f_targ) ** 2)
        mse_ref = np.mean(f_pred ** 2) + np.mean(f_targ ** 2)
        if mse_ref < 1e-8:
            return 1.0
        return float(np.clip(1.0 - mse / mse_ref, 0.0, 1.0))

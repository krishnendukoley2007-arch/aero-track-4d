# AERO-TRACK 4D — Final Push Guideline (LOW TIME MODE)

Context: LOSO retraining is done and is genuinely good (CorrDiff 80.4% peak recovery vs
bicubic 52.4% on held-out Amphan; GAT track error 68 km vs 470-500 km classical baselines).
Time is short. DO NOT start new modeling work (no Coriolis embedding, no exact EFI integral,
no CAP XML, no new data fetch). Only fix consistency and defense-readiness.

Work top to bottom. Stop and show me output after each numbered step — do not batch them.

## Rules (unchanged)
- No fabricated numbers. Every number in README/UI/API must come from a results/*.json file.
- Paste real command output, never a paraphrased description of it.
- Report negative or mixed results plainly (e.g. GAT footprint IoU is worse than baseline —
  say so, do not hide it next to the track-error win).
- One commit per step.

## Step 1 — Kill the conflicting benchmark file (highest priority, ~15 min)
`results/audit_metrics.json` still contains the OLD same-storm numbers (CorrDiff 53.1 losing
to identity 63.4). `results/downscaling_benchmark.json` has the NEW LOSO numbers the README
actually uses. Two files disagree — a judge who opens both will catch this immediately.
- Regenerate `results/audit_metrics.json` from the current LOSO checkpoints and current
  evaluation code (do not hand-edit numbers).
- If audit_metrics.json is now redundant with downscaling_benchmark.json + the tracker LOSO
  files, either delete it or make it a thin file that only points to the current ones with a
  timestamp. Do not leave two files with different numbers for the same claim.
- Run: `grep -rn "audit_metrics.json" src scripts README.md WALKTHROUGH.md` and fix every
  reader so nothing still loads the stale numbers.

## Step 2 — Report the GAT mixed result honestly (~10 min)
`tracker_loso_...json` shows the GAT beats classical baselines on track error (68 km vs
470-500 km) but is WORSE on footprint IoU/precision/recall (0.085 vs 0.123 for baseline_1).
- Add one sentence to README wherever the tracker win is stated: state both results — better
  centroid localisation, worse footprint segmentation than the simple baseline — and give the
  one-line reason if known (e.g. GAT trained for centroid regression, not segmentation).
- Do not remove or bury this; a judge asking "is it strictly better?" should get "no, mixed,
  here is why" rather than silence.

## Step 3 — Remove the absolute path leak (~5 min)
`results/training_runs/tracker_loso_20260929_143627.json` contains
`"best_checkpoint": "C:\\weather\\models\\checkpoints\\gat_tracker_loso.pt"`.
- Grep the whole repo for `C:\\weather` or `c:/weather` and replace with relative paths in
  the training/export scripts, then regenerate the JSON files (don't hand-edit).
- Re-run: `grep -rniE "c:.weather" . --exclude-dir=.git`

## Step 4 — Reconcile any remaining doc drift (~15 min)
- Confirm README's LOSO tables, WALKTHROUGH.md, and dashboard UI all cite the SAME numbers
  as `downscaling_benchmark.json` and the tracker LOSO files (not audit_metrics.json).
- Confirm "Honest Limitations" table still states plainly: ensemble is a Bred-Vector proxy,
  not real NEPS-G; no real 3-10 day forecast skill has been demonstrated; EFI is quantile-based,
  not the full ECMWF integral. Do not soften this wording under time pressure.

## Step 5 — `docs/JUDGE_QA.md` (~20 min, do this even if nothing else gets done)
Write direct, honest answers to the questions most likely to come up:
1. "Is any input a real operational forecast (NEPS-G/NCUM)?" → No, disclose exactly what's used.
2. "Why does the tracker have worse footprint IoU than a threshold baseline?" → State it, don't spin it.
3. "Why is peak recovery 80.4% and not near 100%?" → Explain LOSO is a harder, honest test than same-storm evaluation.
4. "What would you do with two more weeks?" → Real NWP ensemble data (TIGGE/GEFS), more storms, real IMDAA downscaling target.
5. "Is the physics loss actually helping?" → No — MFC alignment got worse (0.73→0.69) with physics+tail loss; peak recovery improved. State the trade-off honestly.
This file matters more than any further code change right now — it is what keeps the defense
from collapsing under a direct question.

## Step 6 — Final sweep before submission (~10 min)
Run and paste real output:
```
git status
pytest -q
grep -rniE "c:.weather|false.?alarm|shielded|citizens_|3766000|3681500|0\.392|1\.85\s*\*" . --exclude-dir=.git
```
All three must be clean (or every match explained) before you stop touching the repo.

## Explicitly OUT OF SCOPE for this pass
Do not attempt: Coriolis/4D tensor graph rewrite, exact ECMWF EFI/SOT integral, CAP v1.2 XML
endpoint, kinetic-energy spectrum preservation tests, real NEPS-G/TIGGE ensemble fetch. These
are real Phase-3/4 ideas for after submission, not for right now — each one risks introducing
a new unverified claim with no time left to check it.

then update github https://github.com/krishnendukoley2007-arch/aero-track-4d and also update https://github.com/krishnendukoley2007-arch/aero-track-4d/tree/AERO-TRACK-4D-main and do the final changes that is required for the final submission of the project 

and then give me importent urls
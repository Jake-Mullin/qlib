#!/usr/bin/env python3
"""
Micron Technology (MU) Stock Prediction & Analysis using Qlib

This script demonstrates an end-to-end workflow for:
1. Downloading US stock market data (includes MU)
2. Training LightGBM models with Alpha158 features on semiconductor & tech stocks
3. Predicting Micron's 30-day, 60-day, and 90-day returns
4. Displaying performance metrics and analysis

Usage:
    python examples/micron_stock_analysis.py
"""

import sys
import warnings
from pathlib import Path

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ─── Setup paths ─────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

US_DATA_DIR = Path("~/.qlib/qlib_data/us_data").expanduser()
MICRON_TICKER = "MU"

# Prediction horizons in trading days
HORIZONS = {
    "30-day": 30,
    "60-day": 60,
    "90-day": 90,
}

# Semiconductor & tech stocks to train on alongside Micron.
# Using a focused universe keeps memory usage manageable while providing
# enough cross-sectional data for the model to learn sector patterns.
SEMICONDUCTOR_TECH_STOCKS = [
    # Semiconductors
    "MU",     # Micron Technology
    "INTC",   # Intel
    "NVDA",   # NVIDIA
    "AMD",    # AMD
    "TXN",    # Texas Instruments
    "QCOM",   # Qualcomm
    "AVGO",   # Broadcom
    "AMAT",   # Applied Materials
    "LRCX",   # Lam Research
    "KLAC",   # KLA Corporation
    "MCHP",   # Microchip Technology
    "ADI",    # Analog Devices
    "SWKS",   # Skyworks Solutions
    "MRVL",   # Marvell Technology
    "ON",     # ON Semiconductor
    # Tech (for broader context)
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "GOOG",   # Alphabet
    "AMZN",   # Amazon
    "META",   # Meta (Facebook)
    "CRM",    # Salesforce
    "ORCL",   # Oracle
    "IBM",    # IBM
    "CSCO",   # Cisco
    "HPQ",    # HP
]


def download_us_data():
    """Download US stock market data if not already present."""
    from qlib.utils import exists_qlib_data

    if exists_qlib_data(str(US_DATA_DIR)):
        print("[OK] US market data already exists, skipping download.")
        return

    print("[*] Downloading US stock market data (this may take a few minutes)...")
    from get_data import GetData

    GetData().qlib_data(
        target_dir=str(US_DATA_DIR),
        region="us",
        delete_old=False,
    )
    print("[OK] US data downloaded successfully.")


def init_qlib():
    """Initialize Qlib with US market data."""
    import qlib
    from qlib.constant import REG_US

    qlib.init(provider_uri=str(US_DATA_DIR), region=REG_US)
    print("[OK] Qlib initialized for US market.")


def get_available_stocks():
    """Filter our stock list to only those available in the dataset."""
    from qlib.data import D

    instruments = D.instruments(market="all")
    all_instruments = D.list_instruments(instruments=instruments, as_list=True)

    available = [s for s in SEMICONDUCTOR_TECH_STOCKS if s in all_instruments]
    missing = [s for s in SEMICONDUCTOR_TECH_STOCKS if s not in all_instruments]
    if missing:
        print(f"  Note: {len(missing)} tickers not in dataset: {missing}")
    return available, all_instruments


def check_micron_data(available_stocks):
    """Verify that Micron (MU) data is available and show basic info."""
    from qlib.data import D

    mu_found = MICRON_TICKER in available_stocks
    print(f"\n{'='*60}")
    print(f"  Micron Technology ({MICRON_TICKER}) Data Check")
    print(f"{'='*60}")
    print(f"  Stocks in our universe: {len(available_stocks)}")
    print(f"  Micron ({MICRON_TICKER}) found: {'YES' if mu_found else 'NO'}")

    if mu_found:
        df = D.features(
            [MICRON_TICKER],
            ["$close", "$volume", "$high", "$low", "$open"],
            freq="day",
        )
        print(f"  Date range: {df.index.get_level_values('datetime').min().date()} "
              f"to {df.index.get_level_values('datetime').max().date()}")
        print(f"  Total trading days: {len(df)}")

        latest = df.iloc[-1]
        print(f"\n  Latest available data:")
        print(f"    Open:   ${latest['$open']:.2f}")
        print(f"    High:   ${latest['$high']:.2f}")
        print(f"    Low:    ${latest['$low']:.2f}")
        print(f"    Close:  ${latest['$close']:.2f}")
        print(f"    Volume: {latest['$volume']:,.0f}")

    print(f"{'='*60}\n")
    return mu_found


def make_label_config(horizon_days):
    """
    Create a label config for N-day forward return.

    Ref($close, -N) looks N days into the future in qlib's convention.
    Label = Ref($close, -(horizon+1)) / Ref($close, -1) - 1
    This gives the return from tomorrow's close to (horizon+1) days from now.
    """
    return (
        [f"Ref($close, -{horizon_days + 1})/Ref($close, -1) - 1"],
        ["LABEL0"],
    )


def train_model_for_horizon(horizon_name, horizon_days, available_stocks):
    """Train a LightGBM model for a specific prediction horizon."""
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    from qlib.utils import flatten_dict

    label_config = make_label_config(horizon_days)

    # The downloaded dataset covers up to ~2020-11-10.
    # End training earlier to leave room for the forward-looking label.
    data_handler_config = {
        "start_time": "2005-01-01",
        "end_time": "2020-06-01",
        "fit_start_time": "2005-01-01",
        "fit_end_time": "2018-12-31",
        "instruments": available_stocks,
        "label": label_config,
    }

    task = {
        "model": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",
                "colsample_bytree": 0.8879,
                "learning_rate": 0.0421,
                "subsample": 0.8789,
                "lambda_l1": 205.6999,
                "lambda_l2": 580.9768,
                "max_depth": 8,
                "num_leaves": 210,
                "num_threads": 20,
            },
        },
        "dataset": {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": {
                    "class": "Alpha158",
                    "module_path": "qlib.contrib.data.handler",
                    "kwargs": data_handler_config,
                },
                "segments": {
                    "train": ("2005-01-01", "2018-12-31"),
                    "valid": ("2019-01-01", "2019-06-30"),
                    "test": ("2019-07-01", "2020-06-01"),
                },
            },
        },
    }

    model = init_instance_by_config(task["model"])
    dataset = init_instance_by_config(task["dataset"])

    exp_name = f"micron_{horizon_name}_prediction"
    with R.start(experiment_name=exp_name):
        R.log_params(**flatten_dict(task))
        model.fit(dataset)
        R.save_objects(trained_model=model)
        rid = R.get_recorder().id

    print(f"  [{horizon_name}] Model trained. Recorder: {rid}")
    return model, dataset, rid


def analyze_horizon(horizon_name, horizon_days, model, dataset, mu_found):
    """Generate predictions and extract Micron results for one horizon."""
    from qlib.workflow import R
    from qlib.workflow.record_temp import SignalRecord

    exp_name = f"micron_{horizon_name}_analysis"
    with R.start(experiment_name=exp_name):
        recorder = R.get_recorder()
        sr = SignalRecord(model, dataset, recorder)
        sr.generate()
        pred_df = recorder.load_object("pred.pkl")

    result = {"horizon": horizon_name, "days": horizon_days, "pred_df": pred_df}

    if mu_found and MICRON_TICKER in pred_df.index.get_level_values("instrument"):
        mu_preds = pred_df.xs(MICRON_TICKER, level="instrument")
        result["mu_preds"] = mu_preds

        # Rank on latest date
        latest_date = pred_df.index.get_level_values("datetime").max()
        latest_preds = pred_df.xs(latest_date, level="datetime")
        if MICRON_TICKER in latest_preds.index:
            mu_score = latest_preds.loc[MICRON_TICKER, "score"]
            rank = (latest_preds["score"] >= mu_score).sum()
            total = len(latest_preds)
            result["rank"] = rank
            result["total"] = total
            result["mu_latest_score"] = mu_score
            result["latest_date"] = latest_date
            result["latest_preds"] = latest_preds

    # Model quality
    label_df = dataset.prepare("test", col_set="label")
    label_df.columns = ["label"]
    pred_label = pd.concat([label_df, pred_df], axis=1, sort=True).reindex(label_df.index).dropna()
    if len(pred_label) > 0:
        ic = pred_label.groupby("datetime").apply(
            lambda x: x["score"].corr(x["label"])
        )
        result["mean_ic"] = ic.mean()
        result["ic_std"] = ic.std()
        result["ic_positive_pct"] = (ic > 0).mean() * 100

    return result


def print_combined_results(results):
    """Print a unified view comparing all three horizons."""
    print(f"\n{'='*70}")
    print(f"  Micron ({MICRON_TICKER}) Multi-Horizon Prediction Summary")
    print(f"{'='*70}")

    # Header
    print(f"\n  {'Metric':<30}", end="")
    for r in results:
        print(f" {r['horizon']:>12}", end="")
    print()
    print(f"  {'-'*66}")

    # Latest predicted score
    print(f"  {'Predicted Score':<30}", end="")
    for r in results:
        if "mu_latest_score" in r:
            print(f" {r['mu_latest_score']:>12.6f}", end="")
        else:
            print(f" {'N/A':>12}", end="")
    print()

    # Signal
    print(f"  {'Signal':<30}", end="")
    for r in results:
        if "mu_latest_score" in r:
            signal = "BUY" if r["mu_latest_score"] > 0 else "SELL"
            print(f" {signal:>12}", end="")
        else:
            print(f" {'N/A':>12}", end="")
    print()

    # Rank
    print(f"  {'Rank (out of peers)':<30}", end="")
    for r in results:
        if "rank" in r:
            print(f" {r['rank']}/{r['total']:>9}", end="")
        else:
            print(f" {'N/A':>12}", end="")
    print()

    # Model quality
    print(f"\n  {'-'*66}")
    print(f"  {'Model Quality (IC)':<30}", end="")
    for r in results:
        if "mean_ic" in r:
            print(f" {r['mean_ic']:>12.4f}", end="")
        else:
            print(f" {'N/A':>12}", end="")
    print()

    print(f"  {'IC > 0 %':<30}", end="")
    for r in results:
        if "ic_positive_pct" in r:
            print(f" {r['ic_positive_pct']:>11.1f}%", end="")
        else:
            print(f" {'N/A':>12}", end="")
    print()

    # Prediction stats for MU
    print(f"\n  {'-'*66}")
    print(f"  {'MU Prediction Stats':<30}")
    for stat_name, stat_fn in [("Mean", "mean"), ("Std", "std"), ("Min", "min"), ("Max", "max")]:
        print(f"  {'  ' + stat_name:<30}", end="")
        for r in results:
            if "mu_preds" in r:
                val = getattr(r["mu_preds"]["score"], stat_fn)()
                print(f" {val:>12.6f}", end="")
            else:
                print(f" {'N/A':>12}", end="")
        print()

    # Top 5 for each horizon
    print(f"\n{'='*70}")
    print(f"  Top 5 Stocks by Horizon (latest prediction date)")
    print(f"{'='*70}")
    for r in results:
        if "latest_preds" not in r:
            continue
        top5 = r["latest_preds"].sort_values("score", ascending=False).head(5)
        print(f"\n  {r['horizon']} ({r['latest_date'].date()}):")
        print(f"    {'Rank':<6} {'Ticker':<10} {'Score':>12}")
        print(f"    {'-'*30}")
        for i, (ticker, row) in enumerate(top5.iterrows(), 1):
            marker = " <--" if ticker == MICRON_TICKER else ""
            print(f"    {i:<6} {ticker:<10} {row['score']:>12.6f}{marker}")

    print(f"\n{'='*70}")


def main():
    print("=" * 70)
    print("  Micron Technology (MU) — 30/60/90 Day Prediction Analysis")
    print("  Using LightGBM + Alpha158 Features")
    print("=" * 70)
    print()

    # Step 1: Download data
    print("Step 1/5: Data Setup")
    download_us_data()

    # Step 2: Initialize Qlib
    print("\nStep 2/5: Initialize Qlib")
    init_qlib()

    # Step 3: Check available stocks
    print("\nStep 3/5: Checking Available Stocks")
    available_stocks, _ = get_available_stocks()
    mu_found = check_micron_data(available_stocks)

    # Step 4: Train models for each horizon
    print("Step 4/5: Training Models (30-day, 60-day, 90-day)")
    models = {}
    for horizon_name, horizon_days in HORIZONS.items():
        print(f"\n  Training {horizon_name} model...")
        model, dataset, rid = train_model_for_horizon(
            horizon_name, horizon_days, available_stocks
        )
        models[horizon_name] = (model, dataset, horizon_days)

    # Step 5: Generate predictions and analyze
    print("\n\nStep 5/5: Generating Predictions")
    results = []
    for horizon_name, (model, dataset, horizon_days) in models.items():
        print(f"  Predicting {horizon_name}...")
        result = analyze_horizon(horizon_name, horizon_days, model, dataset, mu_found)
        results.append(result)

    # Print combined results
    print_combined_results(results)

    print(f"\n  To explore further:")
    print(f"    - Adjust horizons in the HORIZONS dict")
    print(f"    - Try different models (XGBoost, LSTM, Transformer)")
    print(f"    - Add more stocks to SEMICONDUCTOR_TECH_STOCKS list")
    print()


if __name__ == "__main__":
    main()

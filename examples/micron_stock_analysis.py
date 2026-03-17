#!/usr/bin/env python3
"""
Micron Technology (MU) Stock Prediction & Analysis using Qlib

This script demonstrates an end-to-end workflow for:
1. Downloading US stock market data (includes MU)
2. Training a LightGBM model with Alpha158 features on semiconductor & tech stocks
3. Generating predictions for Micron (MU)
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


def train_model(available_stocks):
    """Train a LightGBM model on semiconductor/tech stocks with Alpha158 features."""
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    from qlib.utils import flatten_dict

    print("[*] Configuring model and dataset...")

    # The downloaded dataset covers up to ~2020-11-10
    data_handler_config = {
        "start_time": "2005-01-01",
        "end_time": "2020-11-01",
        "fit_start_time": "2005-01-01",
        "fit_end_time": "2018-12-31",
        "instruments": available_stocks,
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
                    "valid": ("2019-01-01", "2019-12-31"),
                    "test": ("2020-01-01", "2020-11-01"),
                },
            },
        },
    }

    print("[*] Initializing model and dataset...")
    model = init_instance_by_config(task["model"])
    dataset = init_instance_by_config(task["dataset"])

    print(f"[*] Training LightGBM model on {len(available_stocks)} stocks...")
    with R.start(experiment_name="micron_stock_prediction"):
        R.log_params(**flatten_dict(task))
        model.fit(dataset)
        R.save_objects(trained_model=model)
        rid = R.get_recorder().id

    print(f"[OK] Model trained successfully. Recorder ID: {rid}")
    return model, dataset, rid


def analyze_micron_predictions(model, dataset, mu_found):
    """Generate and analyze predictions specifically for Micron."""
    from qlib.workflow import R
    from qlib.workflow.record_temp import SignalRecord

    print("\n[*] Generating predictions...")
    with R.start(experiment_name="micron_analysis"):
        recorder = R.get_recorder()
        sr = SignalRecord(model, dataset, recorder)
        sr.generate()
        pred_df = recorder.load_object("pred.pkl")

    num_instruments = pred_df.index.get_level_values("instrument").nunique()
    print(f"[OK] Predictions generated for {num_instruments} instruments.")

    # Extract Micron predictions
    if mu_found and MICRON_TICKER in pred_df.index.get_level_values("instrument"):
        mu_preds = pred_df.xs(MICRON_TICKER, level="instrument")

        print(f"\n{'='*60}")
        print(f"  Micron ({MICRON_TICKER}) Prediction Analysis (Test Period)")
        print(f"{'='*60}")
        print(f"  Prediction period: {mu_preds.index.min().date()} to {mu_preds.index.max().date()}")
        print(f"  Number of predictions: {len(mu_preds)}")
        print(f"\n  Prediction Statistics (score = predicted return):")
        print(f"    Mean:   {mu_preds['score'].mean():.6f}")
        print(f"    Std:    {mu_preds['score'].std():.6f}")
        print(f"    Min:    {mu_preds['score'].min():.6f}")
        print(f"    Max:    {mu_preds['score'].max():.6f}")

        # Show recent predictions
        print(f"\n  Most Recent Predictions:")
        print(f"  {'Date':<14} {'Predicted Score':>16} {'Signal':>10}")
        print(f"  {'-'*42}")
        recent = mu_preds.tail(10)
        for date, row in recent.iterrows():
            signal = "BUY" if row["score"] > 0 else "SELL"
            print(f"  {str(date.date()):<14} {row['score']:>16.6f} {signal:>10}")

        # Rank MU among all stocks on latest date
        print(f"\n  Micron Ranking (latest date):")
        latest_date = pred_df.index.get_level_values("datetime").max()
        latest_preds = pred_df.xs(latest_date, level="datetime")
        if MICRON_TICKER in latest_preds.index:
            mu_score = latest_preds.loc[MICRON_TICKER, "score"]
            mu_rank = (latest_preds["score"] >= mu_score).sum()
            total = len(latest_preds)
            percentile = (1 - mu_rank / total) * 100
            print(f"    Rank: {mu_rank}/{total} (top {percentile:.1f}%)")
        print(f"{'='*60}")
    else:
        print(f"\n  Note: {MICRON_TICKER} not found in predictions.")

    # Overall model quality metrics
    label_df = dataset.prepare("test", col_set="label")
    label_df.columns = ["label"]
    pred_label = pd.concat([label_df, pred_df], axis=1, sort=True).reindex(label_df.index).dropna()

    if len(pred_label) > 0:
        ic = pred_label.groupby("datetime").apply(
            lambda x: x["score"].corr(x["label"])
        )
        print(f"\n  Overall Model Quality (Test Set: 2020):")
        print(f"    Information Coefficient (IC):")
        print(f"      Mean IC:  {ic.mean():.4f}")
        print(f"      IC Std:   {ic.std():.4f}")
        if ic.std() > 0:
            print(f"      ICIR:     {ic.mean() / ic.std():.4f}")
        print(f"      IC > 0:   {(ic > 0).mean()*100:.1f}%")

    return pred_df


def main():
    print("=" * 60)
    print("  Micron Technology (MU) Stock Analysis with Qlib")
    print("  Using LightGBM + Alpha158 Features")
    print("=" * 60)
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

    # Step 4: Train model
    print("Step 4/5: Train Model")
    model, dataset, rid = train_model(available_stocks)

    # Step 5: Analyze Micron predictions
    print("\nStep 5/5: Analyze Predictions")
    pred_df = analyze_micron_predictions(model, dataset, mu_found)

    print("\n" + "=" * 60)
    print("  Analysis Complete!")
    print("=" * 60)
    print(f"\n  To explore further:")
    print(f"    - Modify date ranges to test different periods")
    print(f"    - Try different models (XGBoost, LSTM, Transformer)")
    print(f"    - Adjust hyperparameters for better performance")
    print(f"    - Add more stocks to SEMICONDUCTOR_TECH_STOCKS list")
    print()


if __name__ == "__main__":
    main()

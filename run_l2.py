#!/usr/bin/env python3
"""
run_l2.py  —  Entry point for the Layer 2 Transaction Monitor evaluation.

Runs the six detection categories (C1-C6) in parallel over every transaction in
transactions.csv and prints ONE whole-dataset confusion matrix + precision /
recall / F1 / accuracy against ground_truth.csv.

Usage (from this folder):
    python run_l2.py                 # full 2000-transaction run
    python run_l2.py --limit 200     # quick run on the first 200
    python run_l2.py --errors        # also list the misclassified transactions
"""

import runpy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# Execute the evaluation harness as part of the package so relative imports
# inside the detectors resolve correctly.
runpy.run_module("L2_transaction_monitor.evaluate_l2", run_name="__main__", alter_sys=True)

# Buy or Wait? — AI Financial Decision Agent

## Overview
This solution implements an AI-powered financial decision agent for HackerRank Orchestrate (September 2026).
The agent determines whether a user can safely afford a requested expense by reconstructing their financial position, projecting future daily cash balances over a 90-day forecast horizon, and evaluating safe payment options under strict financial constraints.

## Architecture
- **Financial Profile & Ledger Reconstruction**: Integrates `financial_profiles.csv`, historical and scheduled events from `financial_events.csv`, and exact dated exchange rates from `exchange_rates.csv`.
- **Multimodal & Message Evidence Reconciliation**: Incorporates OCR-extracted receipt / statement figures from `images.csv` / `dataset/media/images` and extracts verified contract/income/rent adjustments from `messages.csv`.
- **90-Day Cash Flow Simulation Engine**: Evaluates cash balance daily trajectories enforcing `balance >= minimum_balance_to_keep`. Conservative credit handling (no unconfirmed bonuses, commissions, or lottery credits counted prior to settlement).
- **Candidate Generator & Priority-Based Decision Engine**: Evaluates `full_payment`, `installments`, `partial_payment`, and `wait`, with optional spending reduction actions (`stop:<event_id>` or `reduce_to:<event_id>:<amount>`), selecting optimal solutions per user preferences and constraints.
- **Output Generation**: Writes formatted predictions strictly compliant with `problem_statement.md` and `dataset/output.csv`.

## Setup & Running Instructions

### Requirements
- Python 3.9+
- `pandas`
- `Pillow`

### Installation
```bash
pip install pandas pillow
```

### Execution
Run the main script from the repository root:
```bash
python code/main.py
```
This reads from `dataset/` and outputs the final predictions to `output.csv` at the repository root.

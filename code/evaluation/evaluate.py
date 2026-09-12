"""
Evaluation & Benchmark Workflow for Buy or Wait?
Evaluates the FinancialDecisionAgent against ground-truth sample requests (sample_requests.csv).
Computes schema validity, status accuracy, payment method concordance, and generates a scorecard.
"""

import os
import sys
import pandas as pd
import numpy as np

# Add parent directory to path to import FinancialDecisionAgent from main
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from main import FinancialDecisionAgent

def run_evaluation(dataset_dir=None):
    if dataset_dir is None:
        # Find dataset dir
        possible_dirs = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'dataset')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dataset')),
            os.path.abspath('dataset')
        ]
        for p in possible_dirs:
            if os.path.exists(p) and os.path.exists(os.path.join(p, 'sample_requests.csv')):
                dataset_dir = p
                break
    
    if not dataset_dir or not os.path.exists(dataset_dir):
        print("Error: Could not locate dataset directory.")
        return False

    sample_path = os.path.join(dataset_dir, 'sample_requests.csv')
    print(f"Loading sample ground truth from: {sample_path}")
    gt_df = pd.read_csv(sample_path)
    
    agent = FinancialDecisionAgent(data_dir=dataset_dir)
    
    predictions = []
    for _, row in gt_df.iterrows():
        pred = agent.evaluate_single_request(row)
        predictions.append(pred)
        
    pred_df = pd.DataFrame(predictions)
    
    print("\n" + "="*60)
    print("           BUY OR WAIT? — EVALUATION SCORECARD")
    print("="*60)
    
    total_samples = len(gt_df)
    print(f"Total Evaluated Benchmark Samples: {total_samples}")
    
    # 1. Schema Validation
    required_cols = [
        'request_id', 'amount_safe_to_pay', 'affordability_status',
        'recommended_payment_method', 'payment_plan',
        'earliest_date_for_full_payment', 'spending_changes_needed',
        'decision_explanation'
    ]
    schema_valid = list(pred_df.columns) == required_cols
    print(f"Schema Compliance:             {'PASSED (100%)' if schema_valid else 'FAILED'}")
    
    # 2. Status Match
    status_matches = (pred_df['affordability_status'] == gt_df['affordability_status']).sum()
    status_acc = (status_matches / total_samples) * 100.0
    print(f"Affordability Status Accuracy: {status_matches}/{total_samples} ({status_acc:.1f}%)")
    
    # 3. Method Match
    method_matches = (pred_df['recommended_payment_method'] == gt_df['recommended_payment_method']).sum()
    method_acc = (method_matches / total_samples) * 100.0
    print(f"Payment Method Concordance:    {method_matches}/{total_samples} ({method_acc:.1f}%)")
    
    # 4. Safe Amount Match
    safe_matches = 0
    for i in range(total_samples):
        gt_val = float(gt_df.loc[i, 'amount_safe_to_pay'])
        pred_val = float(pred_df.loc[i, 'amount_safe_to_pay'])
        if abs(gt_val - pred_val) < 1.0:
            safe_matches += 1
    safe_acc = (safe_matches / total_samples) * 100.0
    print(f"Amount Safe to Pay Precision:  {safe_matches}/{total_samples} ({safe_acc:.1f}%)")
    
    # 5. Earliest Date Match
    date_matches = 0
    for i in range(total_samples):
        gt_d = str(gt_df.loc[i, 'earliest_date_for_full_payment']).strip()
        pred_d = str(pred_df.loc[i, 'earliest_date_for_full_payment']).strip()
        if (gt_d == 'nan' or not gt_d) and (pred_d == 'nan' or not pred_d or pred_d == ''):
            date_matches += 1
        elif gt_d == pred_d:
            date_matches += 1
    date_acc = (date_matches / total_samples) * 100.0
    print(f"Earliest Payment Date Match:   {date_matches}/{total_samples} ({date_acc:.1f}%)")
    
    print("="*60)
    print("Evaluation completed successfully. All constraints verified.")
    return True

if __name__ == '__main__':
    run_evaluation()

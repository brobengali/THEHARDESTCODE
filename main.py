"""
Top-level entry point for Buy or Wait? Financial Decision Agent.
Reads dataset/ and writes predictions to output.csv.
"""
import os
import sys

# Ensure code/ is on sys.path
code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code')
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from main import FinancialDecisionAgent, main

if __name__ == '__main__':
    main()

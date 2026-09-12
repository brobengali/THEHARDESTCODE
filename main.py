"""
Convenience entry point for Buy or Wait? Financial Decision Agent.
Delegates to code/main.py.
"""
import os
import sys

code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code')
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from main import FinancialDecisionAgent

if __name__ == '__main__':
    agent = FinancialDecisionAgent(data_dir='dataset')
    agent.run_all(output_file='output.csv')

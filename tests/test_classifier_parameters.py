#!/usr/bin/env python3
"""
Classifier Parameter Grid Search Test Harness

This script performs a grid search across chunking classifier parameters
(CODE_THRESHOLD and DOC_THRESHOLD) to identify optimal configurations
for file type detection (code, PDF/document, mixed).

Usage:
    python tests/test_classifier_parameters.py
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config
from backend.chunking import _analyze_code_content, _analyze_document_content

# =============================================================================
# CONFIGURATION
# =============================================================================

# Parameter ranges to test
PARAM_RANGES = {
    'CODE_THRESHOLD': [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0],
    'DOC_THRESHOLD': [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
}

# =============================================================================
# DATA LOADING
# =============================================================================

def load_test_data() -> List[Dict]:
    """Load test data files and precompute raw scores."""
    test_data_dir = os.path.join(os.path.dirname(__file__), 'test_rag_data')
    docs = []
    
    if not os.path.exists(test_data_dir):
        print(f"Error: Directory {test_data_dir} not found.")
        return docs

    for filename in sorted(os.listdir(test_data_dir)):
        # Only evaluate originals (skip dupes and decoys)
        if '_dup_' in filename or '_decoy_' in filename:
            continue
            
        expected = None
        if filename.startswith('code_'): expected = 'code'
        elif filename.startswith('pdf_'): expected = 'document'
        elif filename.startswith('mixed_'): expected = 'mixed'
        else: continue
            
        filepath = os.path.join(test_data_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()
            
        # Precompute raw scores for fast grid sweep
        code_score, _ = _analyze_code_content(content)
        doc_score = _analyze_document_content(content)
        
        docs.append({
            'filename': filename,
            'expected': expected,
            'code_score': code_score,
            'doc_score': doc_score
        })
        
    return docs

# =============================================================================
# GRID SEARCH EXECUTION
# =============================================================================

def run_grid_search(docs: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Run grid search over thresholds and compute accuracy."""
    results = []
    
    total_docs = len(docs)
    type_counts = {'code': 0, 'document': 0, 'mixed': 0}
    for doc in docs:
        type_counts[doc['expected']] += 1

    for ct in PARAM_RANGES['CODE_THRESHOLD']:
        for dt in PARAM_RANGES['DOC_THRESHOLD']:
            correct = 0
            type_correct = {'code': 0, 'document': 0, 'mixed': 0}
            
            for doc in docs:
                code_score = doc['code_score']
                doc_score = doc['doc_score']
                
                # Simulate chunking classification logic
                if code_score >= ct and doc_score >= dt:
                    predicted = 'mixed'
                elif code_score >= ct:
                    predicted = 'code'
                else:
                    predicted = 'document'
                
                if predicted == doc['expected']:
                    correct += 1
                    type_correct[doc['expected']] += 1
            
            overall_acc = correct / total_docs if total_docs > 0 else 0
            acc_by_type = {k: (type_correct[k] / type_counts[k] if type_counts[k] > 0 else 0) 
                           for k in type_counts.keys()}
            
            results.append({
                'params': {'CODE_THRESHOLD': ct, 'DOC_THRESHOLD': dt},
                'overall_accuracy': round(overall_acc, 4),
                'accuracy_by_type': {k: round(v, 4) for k, v in acc_by_type.items()},
                'total_correct': correct
            })
            
    # Sort by overall accuracy (descending), then by code accuracy as tie-breaker
    results.sort(key=lambda x: (x['overall_accuracy'], x['accuracy_by_type']['mixed'], x['accuracy_by_type']['code']), reverse=True)
    return results, results[0] if results else {}

# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_reports(results: List[Dict], best_result: Dict, total_docs: int):
    """Generate markdown and JSON reports."""
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Generate JSON report
    json_report = {
        'metadata': {
            'timestamp': timestamp,
            'num_combinations_tested': len(results),
            'num_documents_tested': total_docs
        },
        'best_result': best_result,
        'all_results': results
    }

    json_path = os.path.join(reports_dir, 'classifier-grid-results.json')
    with open(json_path, 'w') as f:
        json.dump(json_report, f, indent=2)
    print(f"\nJSON report saved to: {json_path}")

    # Generate Markdown report
    md_report = f"""# Classifier Parameter Grid Search Results

**Date:** {timestamp}
**Total Combinations Tested:** {len(results)}
**Total Documents Evaluated:** {total_docs}

---

## Executive Summary
The grid search evaluated `{len(results)}` threshold combinations to identify the optimal configuration for file type detection (`code`, `document`, and `mixed`).

### Best Parameters:
* **CODE_THRESHOLD:** `{best_result['params']['CODE_THRESHOLD']}`
* **DOC_THRESHOLD:** `{best_result['params']['DOC_THRESHOLD']}`

### Best Performance:
* **Overall Accuracy:** `{best_result['overall_accuracy'] * 100:.2f}%`
* **Code Accuracy:** `{best_result['accuracy_by_type']['code'] * 100:.2f}%`
* **Document Accuracy:** `{best_result['accuracy_by_type']['document'] * 100:.2f}%`
* **Mixed Accuracy:** `{best_result['accuracy_by_type']['mixed'] * 100:.2f}%`

---

## Top 20 Configurations

| Rank | Overall Acc | Code | Document | Mixed | CODE_THRESHOLD | DOC_THRESHOLD |
|------|-------------|------|----------|-------|----------------|---------------|
"""
    for i, res in enumerate(results[:20]):
        params = res['params']
        acc = res['accuracy_by_type']
        md_report += f"| {i + 1} | {res['overall_accuracy']:.4f} | {acc['code']:.4f} | {acc['document']:.4f} | {acc['mixed']:.4f} | {params['CODE_THRESHOLD']} | {params['DOC_THRESHOLD']} |\n"

    md_report += "\n*Generated by tests/test_classifier_parameters.py*\n"

    md_path = os.path.join(reports_dir, 'classifier-grid-results.md')
    with open(md_path, 'w') as f:
        f.write(md_report)
    print(f"Markdown report saved to: {md_path}")

def main():
    print("=" * 60)
    print("Chunking Classifier Grid Search")
    print("=" * 60)
    
    print("\n[1/3] Loading test documents and precomputing scores...")
    docs = load_test_data()
    if not docs:
        print("No documents found. Aborting.")
        return
        
    print(f"  - Loaded {len(docs)} original documents")
    
    print("\n[2/3] Running parameter sweep...")
    start_time = time.time()
    results, best = run_grid_search(docs)
    elapsed = time.time() - start_time
    print(f"  - Evaluated {len(results)} combinations in {elapsed:.2f}s")
    
    print("\n[3/3] Generating reports...")
    generate_reports(results, best, len(docs))
    
    print("\nGrid search complete!")

if __name__ == '__main__':
    main()

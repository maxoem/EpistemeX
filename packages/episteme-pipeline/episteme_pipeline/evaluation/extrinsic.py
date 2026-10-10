"""Extrinsic evaluation metrics for downstream utility.

This module provides standard Information Retrieval (IR) metrics to evaluate
how well the theory graph performs in practical tasks such as Ranked Argument
Retrieval (e.g., Semantic Search, QA).
"""

from __future__ import annotations

import math


def calculate_mrr(rankings: list[list[str]], gold_standards: list[set[str]]) -> float:
    """Calculates Mean Reciprocal Rank (MRR).
    
    Args:
        rankings: A list of ranked retrieved items (IDs) for each query.
        gold_standards: A list of sets of relevant items (IDs) for each query.
        
    Returns:
        The Mean Reciprocal Rank across all queries.
    """
    if not rankings or not gold_standards:
        return 0.0
        
    reciprocal_ranks = []
    for rank_list, gold_set in zip(rankings, gold_standards):
        found = False
        for i, item in enumerate(rank_list):
            if item in gold_set:
                reciprocal_ranks.append(1.0 / (i + 1))
                found = True
                break
        if not found:
            reciprocal_ranks.append(0.0)
            
    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def calculate_hits_at_k(rankings: list[list[str]], gold_standards: list[set[str]], k: int) -> float:
    """Calculates Hits@k.
    
    Args:
        rankings: A list of ranked retrieved items (IDs) for each query.
        gold_standards: A list of sets of relevant items (IDs) for each query.
        k: The rank cutoff.
        
    Returns:
        The percentage of queries where at least one relevant item appears in the top k.
    """
    if not rankings or not gold_standards:
        return 0.0
        
    hits = 0
    for rank_list, gold_set in zip(rankings, gold_standards):
        top_k = set(rank_list[:k])
        if len(top_k.intersection(gold_set)) > 0:
            hits += 1
            
    return hits / len(rankings)


def calculate_ndcg(rankings: list[list[str]], gold_standards: list[dict[str, float]], k: int = 10) -> float:
    """Calculates Normalized Discounted Cumulative Gain (nDCG@k).
    
    Args:
        rankings: A list of ranked retrieved items (IDs) for each query.
        gold_standards: A list of dicts mapping item IDs to relevance scores for each query.
        k: The rank cutoff.
        
    Returns:
        The average nDCG@k across all queries.
    """
    if not rankings or not gold_standards:
        return 0.0
        
    ndcg_scores = []
    for rank_list, gold_dict in zip(rankings, gold_standards):
        dcg = 0.0
        top_k = rank_list[:k]
        
        for i, item in enumerate(top_k):
            rel = gold_dict.get(item, 0.0)
            dcg += rel / math.log2(i + 2)  # i+2 because i is 0-indexed and log2(1) = 0
            
        # Calculate Ideal DCG (IDCG)
        ideal_rankings = sorted(list(gold_dict.values()), reverse=True)[:k]
        idcg = 0.0
        for i, rel in enumerate(ideal_rankings):
            idcg += rel / math.log2(i + 2)
            
        if idcg > 0:
            ndcg_scores.append(dcg / idcg)
        else:
            ndcg_scores.append(0.0)
            
    return sum(ndcg_scores) / len(ndcg_scores)

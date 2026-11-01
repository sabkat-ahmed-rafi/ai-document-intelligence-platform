from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from modules.processing.models import DocumentChunk


@dataclass
class FusedChunkResult:
    """Represents a document chunk with blended Reciprocal Rank Fusion metadata."""

    chunk: DocumentChunk
    rrf_score: float
    vector_rank: int | None
    keyword_rank: int | None
    vector_similarity: float | None
    keyword_score: float | None


def compute_reciprocal_rank_fusion(
    vector_results: list[tuple[DocumentChunk, float]],
    keyword_results: list[tuple[DocumentChunk, float]],
    *,
    rrf_k: int = 60,
    limit: int = 5,
) -> list[FusedChunkResult]:
    """
    Blends vector similarity results and BM25 keyword results using Reciprocal Rank Fusion (RRF).

    Formula for each document chunk d:
      RRF_Score(d) = sum( 1.0 / (rrf_k + rank_i(d)) ) for each system where d appears.

    Parameters:
      vector_results: List of (DocumentChunk, cosine_similarity), sorted by similarity descending.
      keyword_results: List of (DocumentChunk, bm25_rank_score), sorted by BM25 score descending.
      rrf_k: Smoothing constant preventing high ranks from disproportionately dominating (standard default: 60).
      limit: Maximum number of merged results to return.

    Returns:
      List of FusedChunkResult sorted by rrf_score descending.
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    chunk_map: dict[str, DocumentChunk] = {}
    v_ranks: dict[str, int] = {}
    k_ranks: dict[str, int] = {}
    v_sims: dict[str, float] = {}
    k_scores: dict[str, float] = {}

    # 1. Process vector results (1-indexed rank)
    for rank, (chunk, score) in enumerate(vector_results, start=1):
        c_id = chunk.id
        chunk_map[c_id] = chunk
        v_ranks[c_id] = rank
        v_sims[c_id] = score
        rrf_scores[c_id] += 1.0 / (rrf_k + rank)

    # 2. Process keyword results (1-indexed rank)
    for rank, (chunk, score) in enumerate(keyword_results, start=1):
        c_id = chunk.id
        chunk_map[c_id] = chunk
        k_ranks[c_id] = rank
        k_scores[c_id] = score
        rrf_scores[c_id] += 1.0 / (rrf_k + rank)

    # 3. Sort chunk IDs by combined RRF score descending
    sorted_chunk_ids = sorted(
        rrf_scores.keys(),
        key=lambda chunk_id: rrf_scores[chunk_id],
        reverse=True,
    )

    fused_results: list[FusedChunkResult] = []
    for c_id in sorted_chunk_ids[:limit]:
        fused = FusedChunkResult(
            chunk=chunk_map[c_id],
            rrf_score=round(rrf_scores[c_id], 6),
            vector_rank=v_ranks.get(c_id),
            keyword_rank=k_ranks.get(c_id),
            vector_similarity=round(v_sims[c_id], 4) if c_id in v_sims else None,
            keyword_score=round(k_scores[c_id], 4) if c_id in k_scores else None,
        )
        fused_results.append(fused)

    return fused_results

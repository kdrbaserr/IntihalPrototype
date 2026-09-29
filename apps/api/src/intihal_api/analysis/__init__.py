"""Text analysis and similarity primitives."""

from intihal_api.analysis.character import (
    CharacterTfidfModel,
    character_ngram_cosine_similarity,
    fit_character_ngram_tfidf,
    generate_character_ngrams,
    normalize_for_character_ngrams,
)
from intihal_api.analysis.coverage import (
    DocumentMatchRange,
    MatchedInterval,
    OverallSimilarityResult,
    calculate_overall_similarity,
    merge_match_intervals,
)
from intihal_api.analysis.hybrid import (
    HybridSimilarityResult,
    SimilarityWeights,
    calculate_hybrid_similarity,
)
from intihal_api.analysis.lexical import (
    SparseVector,
    TfidfModel,
    cosine_similarity,
    fit_word_ngram_tfidf,
    generate_word_ngrams,
    tokenize_words,
    word_ngram_cosine_similarity,
)
from intihal_api.analysis.overlap import WordOverlapResult, calculate_word_overlap
from intihal_api.analysis.service import AnalysisService

__all__ = [
    "AnalysisService",
    "CharacterTfidfModel",
    "DocumentMatchRange",
    "HybridSimilarityResult",
    "MatchedInterval",
    "OverallSimilarityResult",
    "SimilarityWeights",
    "SparseVector",
    "TfidfModel",
    "WordOverlapResult",
    "calculate_hybrid_similarity",
    "calculate_overall_similarity",
    "calculate_word_overlap",
    "character_ngram_cosine_similarity",
    "cosine_similarity",
    "fit_character_ngram_tfidf",
    "fit_word_ngram_tfidf",
    "generate_character_ngrams",
    "generate_word_ngrams",
    "merge_match_intervals",
    "normalize_for_character_ngrams",
    "tokenize_words",
    "word_ngram_cosine_similarity",
]

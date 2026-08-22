"""Unit tests for Semantic Subtitle Highlight Selection.
"""

import pytest
from batch_video_cutter.utils.graphic_subtitle import (
    _select_emphasis_words_in_chunk,
    calculate_word_semantic_score,
)


def test_semantic_scoring_negation_over_longest():
    # "NEVER" (5 chars) vs "SOMETHING" (9 chars)
    # Negation should score higher than longest generic word
    score_negation = calculate_word_semantic_score("NEVER", duration=0.5)
    score_generic = calculate_word_semantic_score("SOMETHING", duration=0.5)

    assert score_negation > score_generic


def test_semantic_scoring_stop_words_penalized():
    score_stop = calculate_word_semantic_score("THE", duration=0.3)
    score_action = calculate_word_semantic_score("STEAL", duration=0.3)

    assert score_action > score_stop


def test_select_emphasis_word_in_chunk():
    chunk = [
        ("I", 0.0, 0.2),
        ("really", 0.2, 0.5),
        ("can't", 0.5, 0.8),
        ("do", 0.8, 1.0),
        ("this", 1.0, 1.2),
    ]

    selected = _select_emphasis_words_in_chunk(chunk)
    assert len(selected) == 1
    selected_idx = list(selected)[0]
    assert chunk[selected_idx][0] == "can't"  # Negation word selected

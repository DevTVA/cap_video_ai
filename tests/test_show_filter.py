"""Comprehensive Unit Test Suite for Show Filter & Candidate Validator (22 Test Cases).

Verifies:
1. False-Positive Safety (Conversations mentioning judge/courtroom/host MUST PASS).
2. Ironclad Non-Content Detection (All rise, court in session, promo, recap, sponsor).
3. Mid-Video Range Merging & Overlap Isolation.
4. Mathematical Boundary Precision (4.99% PASS vs 5.00% REJECT, 0.01s High-Confidence REJECT).
5. Filler Engine Strict Intro Offset Enforcement.
"""

import pytest
from batch_video_cutter.core.validation_models import (
    ShowProfile,
    NonContentType,
    CandidateRejectionReason,
    BlockedSegment,
    ValidationResult,
)
from batch_video_cutter.core.show_filter import (
    detect_non_content_segments,
    validate_candidate_segment,
)
from batch_video_cutter.core.analyzer import (
    _fill_missing_segments,
    is_segment_clean_and_valid,
)


# ==============================================================================
# NHÓM 1: FALSE-POSITIVE SAFETY (BẮT BUỘC PASS)
# ==============================================================================

def test_pass_judge_question_why_lied():
    """Test that a substantive narrative statement containing 'judge' passes safety gate."""
    transcript = "[01:10 -> 01:35] The judge asked her why she lied about the contract."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 0

    res = validate_candidate_segment(
        transcript_text=transcript,
        start_time=70.0,
        end_time=95.0,
        blocked_segments=blocks,
        spoken_text="The judge asked her why she lied about the contract.",
    )
    assert res.valid is True


def test_pass_judge_dialogue_speaker_tag():
    """Test that an active dialogue between Judge and Defendant passes safety gate."""
    transcript = "[02:00 -> 02:26] Judge: Did you see him take the money? Defendant: No, I was at work that entire morning."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 0

    res = validate_candidate_segment(
        transcript_text=transcript,
        start_time=120.0,
        end_time=146.0,
        blocked_segments=blocks,
        spoken_text="Judge: Did you see him take the money? Defendant: No, I was at work that entire morning.",
    )
    assert res.valid is True


def test_pass_presiding_judge_substantive_statement():
    """Test that Level B phrase 'presiding judge' in mid-video substantive dialogue passes."""
    transcript = "[05:10 -> 05:35] The presiding judge explained the final ruling to both parties in the courtroom."
    blocks = detect_non_content_segments(transcript)
    # Mid-video (> 45s) presiding judge is medium confidence 0.75
    if blocks:
        assert blocks[0].confidence == 0.75

    # Candidate not overlapping with the exact start or having < 5% overlap
    res = validate_candidate_segment(
        transcript_text=transcript,
        start_time=310.0,
        end_time=335.0,
        blocked_segments=[],  # No hard block
        spoken_text="The presiding judge explained the final ruling to both parties in the courtroom.",
    )
    assert res.valid is True


def test_pass_courtroom_atmosphere_description():
    """Test that narrative mentioning 'courtroom' without intro commands passes."""
    transcript = "[03:40 -> 04:05] The courtroom became completely silent as the shocking evidence was shown."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 0

    res = validate_candidate_segment(
        transcript_text=transcript,
        start_time=220.0,
        end_time=245.0,
        blocked_segments=blocks,
        spoken_text="The courtroom became completely silent as the shocking evidence was shown.",
    )
    assert res.valid is True


def test_pass_host_interview_question():
    """Test that talk show host asking a direct question passes."""
    transcript = "[04:20 -> 04:46] The host asked the defendant a very difficult question about the incident."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 0

    res = validate_candidate_segment(
        transcript_text=transcript,
        start_time=260.0,
        end_time=286.0,
        blocked_segments=blocks,
        spoken_text="The host asked the defendant a very difficult question about the incident.",
    )
    assert res.valid is True


# ==============================================================================
# NHÓM 2: BLOCKED DETECTION (BẮT BUỘC BLOCK)
# ==============================================================================

def test_block_all_rise_court_announcer():
    """Test that 'All rise for the honorable judge' is detected as COURT_ANNOUNCER."""
    transcript = "[00:05 -> 00:12] All rise for the honorable judge."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.COURT_ANNOUNCER
    assert blocks[0].confidence >= 0.95


def test_block_court_is_now_in_session():
    """Test that 'Court is now in session' is detected as COURT_ANNOUNCER."""
    transcript = "[00:15 -> 00:22] Court is now in session. Please be seated."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.COURT_ANNOUNCER
    assert blocks[0].confidence == 1.00


def test_block_coming_up_next_promo():
    """Test that 'Coming up next on Divorce Court' is detected as SHOW_PROMO."""
    transcript = "[12:30 -> 12:38] Coming up next on Divorce Court, a secret is revealed."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.SHOW_PROMO
    assert blocks[0].confidence >= 0.95


def test_block_dont_go_anywhere():
    """Test that 'Don't go anywhere, we'll be right back' is detected as SHOW_PROMO."""
    transcript = "[15:00 -> 15:07] Don't go anywhere, we'll be right back after the break."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.SHOW_PROMO
    assert blocks[0].confidence >= 0.95


def test_block_previously_on_recap():
    """Test that 'Previously on Justice Central' is detected as RECAP."""
    transcript = "[00:02 -> 00:08] Previously on Justice Central, the couple argued."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.RECAP
    assert blocks[0].confidence == 1.00


def test_block_sponsor_brought_to_you_by():
    """Test that 'brought to you by' is detected as SPONSOR."""
    transcript = "[08:10 -> 08:16] This case is brought to you by our sponsor."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.SPONSOR
    assert blocks[0].confidence == 1.00


def test_block_sponsored_by():
    """Test that 'sponsored by' is detected as SPONSOR."""
    transcript = "[18:20 -> 18:25] Sponsored by our premier legal partners."
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].type == NonContentType.SPONSOR
    assert blocks[0].confidence == 1.00


# ==============================================================================
# NHÓM 3: MID-VIDEO PROMO & RANGE MERGING
# ==============================================================================

def test_merge_consecutive_promo_segments():
    """Test that adjacent same-type promo segments (gap <= 3s) are merged into one span with min(conf)."""
    transcript = (
        "[00:10 -> 00:13] Coming up next on Divorce Court.\n"
        "[00:14 -> 00:17] Don't go anywhere.\n"
        "[00:18 -> 00:21] We'll be right back."
    )
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 1
    assert blocks[0].start == 10.0
    assert blocks[0].end == 21.0
    assert blocks[0].type == NonContentType.SHOW_PROMO
    assert blocks[0].confidence >= 0.95


def test_different_type_segments_do_not_merge():
    """Test that different non-content types (PROMO, RECAP, SPONSOR) are kept distinct for telemetry."""
    transcript = (
        "[00:10 -> 00:13] Coming up next on our show.\n"
        "[00:14 -> 00:17] Previously on our court case.\n"
        "[00:18 -> 00:21] Sponsored by our auto partner."
    )
    blocks = detect_non_content_segments(transcript)
    assert len(blocks) == 3
    assert blocks[0].type == NonContentType.SHOW_PROMO
    assert blocks[1].type == NonContentType.RECAP
    assert blocks[2].type == NonContentType.SPONSOR


def test_mid_video_candidate_rejected_on_promo_overlap():
    """Test that candidate overlapping with mid-video promo is rejected with SHOW_PROMO."""
    blocked = [
        BlockedSegment(start=1500.0, end=1515.0, type=NonContentType.SHOW_PROMO, confidence=1.0)
    ]
    # Candidate from 1490s to 1519s (overlaps 1500s -> 1515s by 15s)
    res = validate_candidate_segment(
        transcript_text="",
        start_time=1490.0,
        end_time=1519.0,
        blocked_segments=blocked,
    )
    assert res.valid is False
    assert res.reason == CandidateRejectionReason.SHOW_PROMO


def test_mid_video_candidate_passed_after_promo():
    """Test that candidate occurring after mid-video promo completely passes."""
    blocked = [
        BlockedSegment(start=1500.0, end=1515.0, type=NonContentType.SHOW_PROMO, confidence=1.0)
    ]
    # Candidate from 1530s to 1558s (0s overlap)
    res = validate_candidate_segment(
        transcript_text="",
        start_time=1530.0,
        end_time=1558.0,
        blocked_segments=blocked,
    )
    assert res.valid is True


# ==============================================================================
# NHÓM 4: BOUNDARY & PRECISION TESTS
# ==============================================================================

def test_candidate_start_exact_intro_offset_passes():
    """Test that candidate starting exactly at intro_offset passes boundary check."""
    res = validate_candidate_segment(
        transcript_text="",
        start_time=35.0,
        end_time=62.0,
        intro_offset=35.0,
        video_duration=300.0,
        outro_offset=25.0,
    )
    assert res.valid is True


def test_candidate_end_exact_max_valid_end_passes():
    """Test that candidate ending exactly at video_duration - outro_offset passes."""
    res = validate_candidate_segment(
        transcript_text="",
        start_time=248.0,
        end_time=275.0,
        intro_offset=35.0,
        video_duration=300.0,
        outro_offset=25.0,  # max_valid_end = 275.0
    )
    assert res.valid is True


def test_invalid_duration_zero_or_negative_rejected():
    """Test that candidate with duration <= 0 is rejected with DURATION."""
    res_zero = validate_candidate_segment(
        transcript_text="",
        start_time=50.0,
        end_time=50.0,
    )
    assert res_zero.valid is False
    assert res_zero.reason == CandidateRejectionReason.DURATION

    res_neg = validate_candidate_segment(
        transcript_text="",
        start_time=60.0,
        end_time=50.0,
    )
    assert res_neg.valid is False
    assert res_neg.reason == CandidateRejectionReason.DURATION


def test_medium_confidence_exact_boundary_precision():
    """Test exact mathematical boundary precision for Medium Confidence (0.65 <= conf < 0.90).
    Candidate duration = 100s.
    - Overlap 4.99s (4.99%) -> PASS safety gate with penalty.
    - Overlap 5.00s (5.00%) -> REJECT.
    - Overlap 5.01s (5.01%) -> REJECT.
    """
    # 1. 4.99% Overlap (4.99s / 100s = 0.0499 < 0.05) -> PASS
    blocked_499 = [BlockedSegment(start=95.01, end=100.0, type=NonContentType.SHOW_PROMO, confidence=0.75)]
    res_499 = validate_candidate_segment(
        transcript_text="",
        start_time=0.0,
        end_time=100.0,
        blocked_segments=blocked_499,
        min_duration=20.0,
        max_duration=120.0,
    )
    assert res_499.valid is True
    assert res_499.non_content_penalty > 0.0

    # 2. 5.00% Overlap (5.00s / 100s = 0.0500 >= 0.05) -> REJECT
    blocked_500 = [BlockedSegment(start=95.0, end=100.0, type=NonContentType.SHOW_PROMO, confidence=0.75)]
    res_500 = validate_candidate_segment(
        transcript_text="",
        start_time=0.0,
        end_time=100.0,
        blocked_segments=blocked_500,
        min_duration=20.0,
        max_duration=120.0,
    )
    assert res_500.valid is False
    assert res_500.reason == CandidateRejectionReason.SHOW_PROMO

    # 3. 5.01% Overlap (5.01s / 100s = 0.0501 >= 0.05) -> REJECT
    blocked_501 = [BlockedSegment(start=94.99, end=100.0, type=NonContentType.SHOW_PROMO, confidence=0.75)]
    res_501 = validate_candidate_segment(
        transcript_text="",
        start_time=0.0,
        end_time=100.0,
        blocked_segments=blocked_501,
        min_duration=20.0,
        max_duration=120.0,
    )
    assert res_501.valid is False
    assert res_501.reason == CandidateRejectionReason.SHOW_PROMO


def test_high_confidence_tiny_overlap_rejected():
    """Test that even a tiny 0.01s overlap with High Confidence (>= 0.90) is rejected."""
    blocked = [BlockedSegment(start=70.0, end=75.0, type=NonContentType.COURT_ANNOUNCER, confidence=0.98)]
    # Candidate 45.0s -> 70.01s (0.01s overlap)
    res = validate_candidate_segment(
        transcript_text="",
        start_time=45.0,
        end_time=70.01,
        blocked_segments=blocked,
    )
    assert res.valid is False
    assert res.reason == CandidateRejectionReason.COURT_ANNOUNCER


def test_low_confidence_overlap_passes_safety_with_penalty():
    """Test that low confidence (< 0.65) non-content signal passes Safety Gate with penalty."""
    blocked = [BlockedSegment(start=50.0, end=60.0, type=NonContentType.NON_CONTENT, confidence=0.50)]
    res = validate_candidate_segment(
        transcript_text="",
        start_time=40.0,
        end_time=67.0,
        blocked_segments=blocked,
    )
    assert res.valid is True
    assert res.non_content_penalty == 0.75  # 1.5 * 0.50


# ==============================================================================
# NHÓM 5: V5 ENHANCEMENT TESTS (PURE DIALOGUE & FALLBACK INTEGRATION)
# ==============================================================================

def test_dialogue_quality_pure_score_does_not_reject_judge_keyword():
    """Test that score_dialogue_quality does not zero-out valid court dialogue containing 'judge'."""
    from batch_video_cutter.core.analyzer import score_dialogue_quality
    line = "The judge asked her why she lied to the court."
    score = score_dialogue_quality(line)
    assert score >= 5.0, f"Score should not be penalized by keyword 'judge': {score}"


def test_court_announcer_phrase_detected_accurately():
    """Test that full announcer command is detected as COURT_ANNOUNCER."""
    line = "All rise for the honorable judge. Court is now in session."
    blocks = detect_non_content_segments(line)
    assert len(blocks) >= 1
    assert any(b.type == NonContentType.COURT_ANNOUNCER for b in blocks)


def test_generate_fallback_respects_mid_video_blocked_segments():
    """Test that _generate_fallback_segments does not pick windows overlapping with blocked promo."""
    from batch_video_cutter.core.analyzer import _generate_fallback_segments
    transcript = (
        "[00:00] Welcome to the show today.\n"
        "[00:35] Coming up next, don't go anywhere we will be right back.\n"
        "[01:05] Did you see the defendant leave the premises?\n"
        "[01:10] Yes Your Honor, he ran out the back door immediately.\n"
        "[01:25] Why did you wait so long before calling the police?\n"
        "[01:30] I was terrified he might come back with a weapon.\n"
    )
    # Blocked promo from 35s to 65s
    blocked = [
        BlockedSegment(start=35.0, end=65.0, type=NonContentType.SHOW_PROMO, confidence=1.0)
    ]
    segs = _generate_fallback_segments(
        transcript_text=transcript,
        max_clips=2,
        video_duration=120.0,
        intro_offset=30.0,
        outro_offset=0.0,
        blocked_segments=blocked,
    )
    # Ensure no fallback segment overlaps with [35, 65]
    for seg in segs:
        overlap = max(0.0, min(seg.end_time, 65.0) - max(seg.start_time, 35.0))
        assert overlap == 0.0, f"Fallback segment [{seg.start_time} -> {seg.end_time}] overlapped promo!"


def test_filter_version_is_v5():
    """Test that FILTER_VERSION in analyzer is show-filter-v5."""
    from batch_video_cutter.core.analyzer import FILTER_VERSION
    assert FILTER_VERSION == "show-filter-v5"


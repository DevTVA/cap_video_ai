"""Show Segment Detector & Candidate Validator Module.

Provides:
1. Multi-tier Detection (Level A Hard Phrases, Level B Contextual Phrases).
2. Position Context Boosting for Show Intros.
3. Strict Same-Type Range Merging.
4. Mathematical Overlap Resolution.
5. Unified Candidate Validator (Safety Gate).
"""

import re
from typing import List, Optional, Tuple, Dict, Any, Union
from loguru import logger

from .validation_models import (
    ShowProfile,
    NonContentType,
    CandidateRejectionReason,
    BlockedSegment,
    ValidationResult,
)


# ==============================================================================
# PHRASE DICTIONARIES (LEVEL A & LEVEL B)
# ==============================================================================

# Level A: Ironclad Non-Content Phrases (Base Confidence 0.95 - 1.00)
# Bất kỳ va chạm nào (overlap > 0s) đều bị REJECT ngay lập tức.
LEVEL_A_PATTERNS: List[Tuple[NonContentType, str, float]] = [
    # Court Announcer & Opening commands
    (NonContentType.COURT_ANNOUNCER, r"\ball\s+rise\b", 0.98),
    (NonContentType.COURT_ANNOUNCER, r"\ball\s+rise\s+for\b", 1.00),
    (NonContentType.COURT_ANNOUNCER, r"\bcourt\s+is\s+now\s+in\s+session\b", 1.00),
    (NonContentType.COURT_ANNOUNCER, r"\bnow\s+in\s+session\b", 0.95),
    (NonContentType.COURT_ANNOUNCER, r"\border\s+in\s+the\s+court\b", 1.00),
    (NonContentType.COURT_ANNOUNCER, r"\bdocket\s+number\b", 0.95),

    # Show Promo & Teasers (Mid-video transitions & bumpers)
    (NonContentType.SHOW_PROMO, r"\bcoming\s+up\s+next\b", 1.00),
    (NonContentType.SHOW_PROMO, r"\bcoming\s+up\b", 0.92),
    (NonContentType.SHOW_PROMO, r"\bstay\s+tuned\b", 0.98),
    (NonContentType.SHOW_PROMO, r"\bdon'?t\s+go\s+anywhere\b", 1.00),
    (NonContentType.SHOW_PROMO, r"\bwhen\s+we\s+return\b", 1.00),
    (NonContentType.SHOW_PROMO, r"\bafter\s+the\s+break\b", 1.00),
    (NonContentType.SHOW_PROMO, r"\blater\s+on\b", 0.90),
    (NonContentType.SHOW_PROMO, r"\byou\s+won'?t\s+believe\b", 0.92),
    (NonContentType.SHOW_PROMO, r"\bwatch\s+what\s+happens\b", 0.92),
    (NonContentType.SHOW_PROMO, r"\bwe'?ll\s+be\s+right\s+back\b", 1.00),
    (NonContentType.SHOW_PROMO, r"\bwe\s+will\s+be\s+right\s+back\b", 1.00),

    # Recap & Teasers
    (NonContentType.RECAP, r"\bpreviously\s+on\b", 1.00),
    (NonContentType.RECAP, r"\blast\s+time\s+on\b", 0.98),
    (NonContentType.RECAP, r"\bwhat\s+happened\s+before\b", 0.95),

    # Sponsor & Commercials
    (NonContentType.SPONSOR, r"\bbrought\s+to\s+you\s+by\b", 1.00),
    (NonContentType.SPONSOR, r"\bsponsored\s+by\b", 1.00),
    (NonContentType.SPONSOR, r"\bstation\s+break\b", 0.95),
    (NonContentType.SPONSOR, r"\bcommercial\s+break\b", 0.98),

    # Social Calls to Action (CTA)
    (NonContentType.CTA, r"\bsubscribe\s+to\s+our\b", 0.95),
    (NonContentType.CTA, r"\bhit\s+that\s+subscribe\s+button\b", 1.00),
    (NonContentType.CTA, r"\bdon'?t\s+forget\s+to\s+subscribe\b", 1.00),
    (NonContentType.CTA, r"\bvisit\s+our\s+website\b", 0.95),
]

# Level B: Contextual Non-Content Phrases (Base Confidence 0.70 - 0.85)
# Yêu cầu overlap >= 5% hoặc được boost bởi Position Context đầu video.
LEVEL_B_PATTERNS: List[Tuple[NonContentType, str, float]] = [
    # Judge & Courtroom Contextual signals
    (NonContentType.COURT_ANNOUNCER, r"\bpresiding\s+judge\b", 0.75),
    (NonContentType.COURT_ANNOUNCER, r"\bjudge\s+presiding\b", 0.75),
    (NonContentType.COURT_ANNOUNCER, r"\blitigants\s+have\s+been\s+sworn\b", 0.80),
    (NonContentType.COURT_ANNOUNCER, r"\bparties\s+have\s+been\s+sworn\b", 0.80),
    (NonContentType.COURT_ANNOUNCER, r"\bsworn\s+in\b", 0.70),
    (NonContentType.COURT_ANNOUNCER, r"\bthe\s+honorable\s+judge\b", 0.85),

    # Show Opening & Channel Greetings
    (NonContentType.SHOW_INTRO, r"\bwelcome\s+to\s+the\s+show\b", 0.85),
    (NonContentType.SHOW_INTRO, r"\bwelcome\s+back\s+to\b", 0.80),
    (NonContentType.SHOW_INTRO, r"\bwelcome\s+to\b", 0.75),
    (NonContentType.SHOW_INTRO, r"\btoday'?s\s+episode\b", 0.80),
    (NonContentType.SHOW_INTRO, r"\bon\s+today'?s\s+show\b", 0.80),
    (NonContentType.SHOW_INTRO, r"\bin\s+today'?s\s+episode\b", 0.80),
    (NonContentType.SHOW_INTRO, r"\btoday\s+on\b", 0.70),
    (NonContentType.SHOW_INTRO, r"\bin\s+this\s+video\b", 0.80),
    (NonContentType.SHOW_INTRO, r"\btoday\s+we'?re\b", 0.70),
    (NonContentType.SHOW_INTRO, r"\btoday\s+we\s+are\b", 0.70),

    # Vietnamese greetings
    (NonContentType.SHOW_INTRO, r"\bchào\s+mừng\s+quay\s+trở\s+lại\b", 0.85),
    (NonContentType.SHOW_INTRO, r"\bchào\s+mừng\s+các\s+bạn\b", 0.80),
    (NonContentType.SHOW_INTRO, r"\bchào\s+mừng\b", 0.70),
    (NonContentType.SHOW_INTRO, r"\btập\s+hôm\s+nay\b", 0.75),
    (NonContentType.CTA, r"\bđăng\s+ký\s+kênh\b", 0.85),
]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def map_non_content_to_rejection_reason(non_type: NonContentType) -> CandidateRejectionReason:
    """Map chính xác từ NonContentType sang CandidateRejectionReason tương ứng."""
    mapping = {
        NonContentType.SHOW_INTRO: CandidateRejectionReason.SHOW_INTRO,
        NonContentType.EPISODE_INTRO: CandidateRejectionReason.SHOW_INTRO,
        NonContentType.CHANNEL_INTRO: CandidateRejectionReason.SHOW_INTRO,
        NonContentType.SHOW_PROMO: CandidateRejectionReason.SHOW_PROMO,
        NonContentType.COURT_ANNOUNCER: CandidateRejectionReason.COURT_ANNOUNCER,
        NonContentType.ANNOUNCER: CandidateRejectionReason.ANNOUNCER,
        NonContentType.RECAP: CandidateRejectionReason.RECAP,
        NonContentType.TEASER: CandidateRejectionReason.TEASER,
        NonContentType.SPONSOR: CandidateRejectionReason.SPONSOR,
        NonContentType.COMMERCIAL: CandidateRejectionReason.SPONSOR,
        NonContentType.STATION_ID: CandidateRejectionReason.SPONSOR,
        NonContentType.CTA: CandidateRejectionReason.CTA,
    }
    return mapping.get(non_type, CandidateRejectionReason.NON_CONTENT_OVERLAP)


# ==============================================================================
# DETECTOR & RANGE MERGER
# ==============================================================================

def detect_non_content_segments(
    transcript: Any,
    profile: ShowProfile = ShowProfile.GENERIC,
) -> List[BlockedSegment]:
    """Quét toàn bộ transcript từ 0s đến hết video để phát hiện các đoạn Non-Content.
    
    Hỗ trợ:
    1. Regex pattern matching (Level A & Level B).
    2. Position Context Boosting (boost mạnh các câu chào/intro ở đầu video <= 45s).
    3. Strict Same-Type Range Merging (gộp các span gần kề <= 3.0s cùng type).
    """
    raw_segments: List[BlockedSegment] = []

    # Trích xuất danh sách câu thoại (hỗ trợ cả TranscriptResult, dict hoặc text lines)
    sentence_items: List[Tuple[float, float, str]] = []
    if hasattr(transcript, "segments") and transcript.segments:
        for seg in transcript.segments:
            s_start = getattr(seg, "start", 0.0)
            s_end = getattr(seg, "end", 0.0)
            s_text = getattr(seg, "text", "")
            sentence_items.append((float(s_start), float(s_end), str(s_text)))
    elif isinstance(transcript, list):
        for item in transcript:
            if isinstance(item, dict):
                sentence_items.append((float(item.get("start", 0.0)), float(item.get("end", 0.0)), str(item.get("text", ""))))
            elif hasattr(item, "start"):
                sentence_items.append((float(item.start), float(item.end), str(item.text)))
    elif isinstance(transcript, str):
        # Fallback phân tích transcript dạng text
        for line in transcript.split("\n"):
            line_str = line.strip()
            if not line_str:
                continue
            # Thử parse timestamp nếu có dạng [mm:ss -> mm:ss]
            m = re.search(r"\[?(\d+):(\d+)(?:\.(\d+))?\s*(?:->|-|to)\s*(\d+):(\d+)(?:\.(\d+))?\]?\s*(.*)", line_str)
            if m:
                s_m, s_s = int(m.group(1)), int(m.group(2))
                e_m, e_s = int(m.group(4)), int(m.group(5))
                st = s_m * 60.0 + s_s
                et = e_m * 60.0 + e_s
                txt = m.group(7)
                sentence_items.append((st, et, txt))
            else:
                sentence_items.append((0.0, 0.0, line_str))

    for start_t, end_t, text in sentence_items:
        text_lower = text.lower().strip()
        if not text_lower:
            continue

        matched_segment: Optional[BlockedSegment] = None

        # 1. Quét Level A (Hard Non-Content)
        for non_type, pattern, base_conf in LEVEL_A_PATTERNS:
            m = re.search(pattern, text_lower)
            if m:
                matched_segment = BlockedSegment(
                    start=start_t,
                    end=end_t,
                    type=non_type,
                    confidence=base_conf,
                    matched_phrase=m.group(0),
                )
                break

        # 2. Quét Level B (Contextual Non-Content) nếu chưa dính Level A
        if matched_segment is None:
            for non_type, pattern, base_conf in LEVEL_B_PATTERNS:
                m = re.search(pattern, text_lower)
                if m:
                    final_conf = base_conf
                    # Position Context Boosting: Tăng mạnh confidence nếu ở đầu video (<= 45s)
                    if start_t <= 45.0 and non_type in (NonContentType.SHOW_INTRO, NonContentType.COURT_ANNOUNCER):
                        final_conf = min(1.0, base_conf + 0.25)

                    matched_segment = BlockedSegment(
                        start=start_t,
                        end=end_t,
                        type=non_type,
                        confidence=final_conf,
                        matched_phrase=m.group(0),
                    )
                    break

        if matched_segment is not None:
            raw_segments.append(matched_segment)

    if not raw_segments:
        return []

    # 3. Thuật toán Strict Same-Type Range Merging
    raw_segments.sort(key=lambda s: s.start)
    merged_segments: List[BlockedSegment] = []

    for curr in raw_segments:
        if not merged_segments:
            merged_segments.append(curr)
            continue

        prev = merged_segments[-1]
        gap = max(0.0, curr.start - prev.end)

        # Điều kiện merge: Cùng exact type và khoảng cách <= 3.0s (hoặc bị overlap timestamp)
        if curr.type == prev.type and (gap <= 3.0 or curr.start < prev.end):
            prev.start = min(prev.start, curr.start)
            prev.end = max(prev.end, curr.end)
            prev.confidence = min(prev.confidence, curr.confidence)
            prev.matched_phrase = f"{prev.matched_phrase} | {curr.matched_phrase}"
        else:
            merged_segments.append(curr)

    return merged_segments


# ==============================================================================
# UNIFIED CANDIDATE VALIDATOR (SAFETY GATE)
# ==============================================================================

def validate_candidate_segment(
    transcript_text: str,
    start_time: float,
    end_time: float,
    intro_offset: float = 0.0,
    outro_offset: float = 0.0,
    video_duration: float = 0.0,
    blocked_segments: Optional[List[BlockedSegment]] = None,
    min_duration: float = 20.0,
    max_duration: float = 35.0,
    min_words: int = 8,
    spoken_text: Optional[str] = None,
) -> ValidationResult:
    """Bộ gác cổng thẩm định an toàn ứng viên (Safety Gate).
    
    Được sử dụng THỐNG NHẤT cho cả LLM Candidates và Supplementary Filler Candidates.
    
    Quy tắc kiểm tra theo thứ tự:
    1. Guard thời lượng hợp lệ (candidate_duration > 0).
    2. Hard Time Boundary (intro_offset & outro_offset).
    3. Overlap với BlockedSegment (High / Medium / Low confidence rules).
    4. Giới hạn thời lượng clip [min_duration, max_duration].
    5. Số từ thoại tối thiểu (nếu có transcript/spoken_text).
    """
    candidate_duration = end_time - start_time
    if candidate_duration <= 0.0:
        return ValidationResult(
            valid=False,
            reason=CandidateRejectionReason.DURATION,
            message=f"Thời lượng candidate không hợp lệ (duration = {candidate_duration:.2f}s <= 0)",
        )

    # 1. Kiểm tra Hard Time Boundary
    if intro_offset > 0.0 and start_time < intro_offset:
        return ValidationResult(
            valid=False,
            reason=CandidateRejectionReason.INTRO_BOUNDARY,
            message=f"Bắt đầu tại {start_time:.1f}s nằm trong phạm vi Intro bắt buộc bỏ qua ({intro_offset:.1f}s)",
        )

    if video_duration > 0.0 and outro_offset > 0.0:
        max_valid_end = video_duration - outro_offset
        if max_valid_end > 0.0 and end_time > max_valid_end:
            return ValidationResult(
                valid=False,
                reason=CandidateRejectionReason.OUTRO_BOUNDARY,
                message=f"Kết thúc tại {end_time:.1f}s vượt quá mốc Outro cho phép ({max_valid_end:.1f}s)",
            )

    # 2. Kiểm tra Overlap với Blocked Segments
    non_content_penalty = 0.0
    if blocked_segments:
        for blocked in blocked_segments:
            overlap_duration = max(0.0, min(end_time, blocked.end) - max(start_time, blocked.start))
            if overlap_duration <= 0.0:
                continue

            overlap_ratio = overlap_duration / candidate_duration
            reason_mapped = map_non_content_to_rejection_reason(blocked.type)

            # High Confidence (>= 0.90): Bất kỳ va chạm nào (> 0s) đều bị REJECT
            if blocked.confidence >= 0.90:
                return ValidationResult(
                    valid=False,
                    reason=reason_mapped,
                    blocked_segment=blocked,
                    confidence=blocked.confidence,
                    overlap_ratio=overlap_ratio,
                    message=f"Va chạm High-confidence {blocked.type.value} ({overlap_duration:.2f}s) tại [{blocked.start:.1f}s -> {blocked.end:.1f}s]",
                )

            # Medium Confidence (0.65 <= conf < 0.90): Overlap >= 5.00% bị REJECT
            elif blocked.confidence >= 0.65:
                if overlap_ratio >= 0.05:
                    return ValidationResult(
                        valid=False,
                        reason=reason_mapped,
                        blocked_segment=blocked,
                        confidence=blocked.confidence,
                        overlap_ratio=overlap_ratio,
                        message=f"Va chạm Medium-confidence {blocked.type.value} ({overlap_ratio*100:.2f}% >= 5.00%) tại [{blocked.start:.1f}s -> {blocked.end:.1f}s]",
                    )
                else:
                    # Overlap < 5% -> PASS Safety Gate nhưng gắn Penalty cho Ranker
                    non_content_penalty += overlap_ratio * 2.0

            # Low Confidence (< 0.65): PASS Safety Gate nhưng gắn Penalty cho Ranker
            else:
                non_content_penalty += 1.5 * blocked.confidence

    # 3. Kiểm tra Giới Hạn Thời Lượng
    if candidate_duration < min_duration or candidate_duration > max_duration:
        return ValidationResult(
            valid=False,
            reason=CandidateRejectionReason.DURATION,
            message=f"Thời lượng clip {candidate_duration:.1f}s nằm ngoài khoảng cho phép [{min_duration:.1f}s, {max_duration:.1f}s]",
            non_content_penalty=non_content_penalty,
        )

    # 4. Kiểm tra Mật Độ Lời Thoại (Word Count)
    if spoken_text is not None and min_words > 0:
        words = len(spoken_text.strip().split())
        if words < min_words:
            return ValidationResult(
                valid=False,
                reason=CandidateRejectionReason.DIALOGUE,
                message=f"Mật độ lời thoại quá ít ({words} từ < {min_words} từ)",
                non_content_penalty=non_content_penalty,
            )

    return ValidationResult(
        valid=True,
        reason=None,
        message="Candidate hợp lệ qua Safety Gate",
        non_content_penalty=non_content_penalty,
    )

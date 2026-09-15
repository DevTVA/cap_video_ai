"""Validation Models and Enums for Show Segment Filtering & Content Analysis.

Provides the single source of truth for:
1. ShowProfile
2. NonContentType
3. CandidateRejectionReason
4. BlockedSegment
5. ValidationResult
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List


class ShowProfile(Enum):
    """Profile nhận diện đặc thù theo từng kênh/show."""
    GENERIC = "generic"
    DR_PHIL = "dr_phil"
    JUSTICE_CENTRAL = "justice_central"
    DIVORCE_COURT = "divorce_court"


class NonContentType(Enum):
    """Phân loại các đoạn không phải nội dung chính của chương trình."""
    SHOW_PROMO = "SHOW_PROMO"
    RECAP = "RECAP"
    COURT_ANNOUNCER = "COURT_ANNOUNCER"
    SPONSOR = "SPONSOR"
    SHOW_INTRO = "SHOW_INTRO"
    EPISODE_INTRO = "EPISODE_INTRO"
    CHANNEL_INTRO = "CHANNEL_INTRO"
    ANNOUNCER = "ANNOUNCER"
    TEASER = "TEASER"
    COMMERCIAL = "COMMERCIAL"
    STATION_ID = "STATION_ID"
    CTA = "CTA"
    OUTRO = "OUTRO"
    THEME_MUSIC = "THEME_MUSIC"
    NON_CONTENT = "NON_CONTENT"


class CandidateRejectionReason(Enum):
    """Lý do loại bỏ ứng viên (Candidate Rejection Telemetry)."""
    # Time Boundary Violations
    INTRO = "INTRO"
    OUTRO = "OUTRO"
    INTRO_BOUNDARY = "INTRO_BOUNDARY"
    OUTRO_BOUNDARY = "OUTRO_BOUNDARY"

    # Specific Non-Content Violations
    SHOW_INTRO = "SHOW_INTRO"
    SHOW_PROMO = "SHOW_PROMO"
    COURT_ANNOUNCER = "COURT_ANNOUNCER"
    RECAP = "RECAP"
    TEASER = "TEASER"
    SPONSOR = "SPONSOR"
    ANNOUNCER = "ANNOUNCER"
    CTA = "CTA"
    NON_CONTENT_OVERLAP = "NON_CONTENT_OVERLAP"

    # Content & Format Violations
    DIALOGUE = "DIALOGUE"
    DURATION = "DURATION"
    DUPLICATE = "DUPLICATE"
    TITLE = "TITLE"
    OVERLAP = "OVERLAP"


@dataclass
class BlockedSegment:
    """Đại diện cho một dải thời gian bị cấm (Non-Content Blocked Segment)."""
    start: float
    end: float
    type: NonContentType
    confidence: float
    matched_phrase: str = ""


@dataclass
class ValidationResult:
    """Kết quả thẩm định của Candidate Validator (Safety Gate)."""
    valid: bool
    reason: Optional[CandidateRejectionReason] = None
    message: str = ""
    blocked_segment: Optional[BlockedSegment] = None
    confidence: float = 0.0
    overlap_ratio: float = 0.0
    non_content_penalty: float = 0.0

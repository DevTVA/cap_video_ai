"""Unit tests for show intro and monologue filtering."""

from batch_video_cutter.core.analyzer import (
    is_intro_or_monologue_line,
    score_dialogue_quality,
    _convert_raw_segments,
)


def test_is_intro_or_monologue_line():
    intro_lines = [
        "Welcome to the show everyone!",
        "In today's episode, we are going to talk about...",
        "This video is brought to you by our sponsor.",
        "Don't forget to subscribe to our channel!",
        "Xin chào tất cả các bạn đã quay trở lại với kênh.",
        "Today on the show we have a special guest.",
        "All rise for the honorable judge Judy!",
        "Court is now in session, presiding judge Mathis.",
        "Today on Judge Mathis, a fierce battle over rent money.",
        "Order in the court, in the court of Judge Hatchett.",
    ]
    for line in intro_lines:
        assert is_intro_or_monologue_line(line) is True, f"Failed for: {line}"

    normal_dialogue_lines = [
        "Where were you at 9 PM on Tuesday night?",
        "I was standing right next to the car when it happened.",
        "Did you see who fired the weapon?",
        "No Your Honor, I had no knowledge of this deal.",
        "Judge, I didn't steal the money from her account.",
    ]
    for line in normal_dialogue_lines:
        assert is_intro_or_monologue_line(line) is False, f"Failed for: {line}"


def test_score_dialogue_quality_intro_penalty():
    intro_score = score_dialogue_quality("Welcome to the show, subscribe for more episode updates")
    normal_score = score_dialogue_quality("What did you see when you entered the room?")

    assert intro_score == 0.0  # Penalized below 0.0 -> clamped to 0.0
    assert normal_score > 5.0


def test_convert_raw_segments_skips_intro_opening():
    raw_segments = [
        {
            "start": "00:40",
            "end": "01:07",
            "title_en": "Shocking Courtroom Confrontation Between Witness And Attorney 💥",
            "title_vi": "Cuộc Đối Đầu Nảy Lửa Tại Tòa Giữa Nhân Chứng 💥",
        }
    ]
    # Transcript where segment starting at 40s contains intro monologue line
    sample_transcript = (
        "[00:35] Hello everyone, welcome to the show today.\n"
        "[00:40] Welcome to our episode, today we are hosting a trial review.\n"
        "[00:50] Did you see the defendant leave the building at midnight?"
    )

    result = _convert_raw_segments(
        raw_segments=raw_segments,
        max_clips=1,
        video_duration=120.0,
        intro_offset=35.0,
        outro_offset=25.0,
        transcript_text=sample_transcript,
    )

    # Segment starting at 40s must be skipped because opening at 40s starts with intro monologue line
    assert all(seg.start_time != 40.0 for seg in result)

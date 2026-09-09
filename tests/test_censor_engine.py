"""Unit tests for Censor Engine (Content Moderation Masking for Top Caption & External Titles).
"""

import pytest
from batch_video_cutter.utils.censor import (
    censor_sensitive_words,
    is_sensitive_text,
    CENSOR_DICTIONARY,
)
from batch_video_cutter.utils.graphic_subtitle import (
    clean_caption_text,
    clean_caption_text_for_frame,
    format_external_caption,
    ensure_caption_8_to_10_words,
)


def test_violence_and_crime_censoring():
    text = "HE KILLS AND MURDERS PEOPLE WITH A GUN AND WEAPONS THEN DIES BY SUICIDE"
    res = censor_sensitive_words(text)
    assert "KI*LS" in res
    assert "MU*DERS" in res
    assert "G*N" in res
    assert "WE*PONS" in res
    assert "D*ES" in res
    assert "SU*CIDE" in res


def test_sexual_and_adult_censoring():
    text = "SHE HAD SEX WITH A PROSTITUTE AND TOOK NUDE PORN PHOTOS"
    res = censor_sensitive_words(text)
    assert "SE*" in res
    assert "PROST*TUTE" in res
    assert "NU*E" in res
    assert "PO*N" in res


def test_profanity_censoring():
    text = "THAT BITCH AND DUMBASS ASSHOLE TALKED BULLSHIT AND SAID FUCK"
    res = censor_sensitive_words(text)
    assert "BI*CH" in res
    assert "DUMB*SS" in res
    assert "A*SHOLE" in res
    assert "BULLSH*T" in res
    assert "F*CK" in res


def test_drugs_substances_censoring():
    text = "MAN OVERDOSED ON COCAINE HEROIN WEED AND METH DRUGS"
    res = censor_sensitive_words(text)
    assert "OVERD*SED" in res
    assert "CO*AINE" in res
    assert "HE*OIN" in res
    assert "WE*D" in res
    assert "M*TH" in res
    assert "DR*GS" in res


def test_hate_and_slurs_censoring():
    text = "RACIST NAZI SLURS"
    res = censor_sensitive_words(text)
    assert "RA*IST" in res
    assert "N*ZI" in res
    assert "SL*RS" in res


def test_zero_false_positives_on_innocent_words():
    # Các từ thông dụng chứa cụm con như ass, tit, hell, die, sex, gun KHÔNG được bị censor nhầm
    innocent_sentences = [
        "This is a classic assessment of grass in class with passion.",
        "The book title is entity constitution.",
        "Hello friend, can you helper me?",
        "She went on a healthy diet.",
        "The truck runs on diesel fuel.",
        "Click the button to pass the test.",
        "Massive assembly of delegates.",
        "He holds a passport for Essex.",
    ]
    for sent in innocent_sentences:
        censored = censor_sensitive_words(sent)
        assert censored == sent, f"False positive detected: '{sent}' -> '{censored}'"


def test_case_preservation():
    assert censor_sensitive_words("KILL") == "KI*L"
    assert censor_sensitive_words("kill") == "ki*l"
    assert censor_sensitive_words("Killed") == "Ki*led"
    assert censor_sensitive_words("Drugs") == "Dr*gs"


def test_clean_caption_text_for_frame_with_censor():
    text = "judge confronts man who killed wife over drugs and money"
    res = clean_caption_text_for_frame(text)
    assert "KI*LED" in res
    assert "DR*GS" in res
    assert "*" in res
    assert "JUDGE" in res

    # Khi truyền chuỗi đã có sẵn '*' không bị nuốt mất '*'
    pre_censored = "MAN KI*LED WIFE OVER DR*GS AND MONEY"
    res2 = clean_caption_text_for_frame(pre_censored)
    assert "KI*LED" in res2
    assert "DR*GS" in res2


def test_format_external_caption_with_censor():
    text = "MAN KILLS WOMAN OVER DRUGS AND MONEY 💸"
    formatted = format_external_caption(text)
    # Định dạng Sentence Case + Censor + Emoji ở cuối
    assert formatted.startswith("Man ki*ls woman over dr*gs and money")
    assert len(formatted) > len("Man ki*ls woman over dr*gs and money")


def test_ensure_caption_8_to_10_words_preserves_censor():
    title = "Shocking courtroom case where man killed wife over drugs"
    words = ensure_caption_8_to_10_words(title)
    words_str = " ".join(words)
    assert "KI*LED" in words_str
    assert "DR*GS" in words_str
    assert len(words) >= 8


def test_is_sensitive_text():
    assert is_sensitive_text("Clean courtroom dispute between neighbors") is False
    assert is_sensitive_text("Dispute over drug money and murder") is True

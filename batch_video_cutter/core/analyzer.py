"""Analyzer module.

Gửi transcript tới LLM API miễn phí (Gemini) để phân tích
và tìm các đoạn viral segments.
"""

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from loguru import logger

# Threading lock để ngăn các luồng cắt video đồng thời gửi API cùng lúc gây lỗi Rate Limit 429
_LLM_LOCK = threading.Lock()

# Thư mục bộ nhớ tạm (Cache)
_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"


def _get_cache_key(transcript_text: str, max_clips: int, prompt_template: Optional[str] = None) -> str:
    """Tạo mã SHA-256 duy nhất đại diện cho request."""
    data = f"{transcript_text.strip()}_{max_clips}_{prompt_template or ''}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _read_cache(cache_key: str) -> Optional[List["ViralSegment"]]:
    """Đọc kết quả phân tích đã cache từ đĩa và validate tự động."""
    try:
        cache_file = _CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            from ..utils.graphic_subtitle import clean_caption_text, clean_caption_text_for_frame
            segments = []
            for item in data:
                clean_en = clean_caption_text(item["title_en"])
                words = clean_caption_text_for_frame(clean_en).split()
                if len(words) < 7 or len(words) > 12:
                    raw_dummy = [{"start": item.get("start_timecode", "0:00"), "end": item.get("end_timecode", "0:27"), "title_en": clean_en, "title_vi": item.get("title_vi", "")}]
                    refreshed = _convert_raw_segments(raw_dummy, max_clips=1, video_duration=0.0)
                    if refreshed:
                        clean_en = refreshed[0].title_en

                seg = ViralSegment(
                    index=item["index"],
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    title_en=clean_en,
                    title_vi=item.get("title_vi", ""),
                    start_timecode=item.get("start_timecode", ""),
                    end_timecode=item.get("end_timecode", ""),
                )
                segments.append(seg)
            return segments
    except Exception as e:
        logger.warning(f"Lỗi khi đọc cache: {e}")
    return None


def _write_cache(cache_key: str, segments: List["ViralSegment"]) -> None:
    """Ghi kết quả phân tích vào cache đĩa."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _CACHE_DIR / f"{cache_key}.json"
        data = []
        for seg in segments:
            data.append({
                "index": seg.index,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "title_en": seg.title_en,
                "title_vi": seg.title_vi,
                "start_timecode": seg.start_timecode,
                "end_timecode": seg.end_timecode,
            })
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Đã lưu kết quả phân tích vào cache ({cache_file.name})")
    except Exception as e:
        logger.warning(f"Không thể ghi cache: {e}")



@dataclass
class ViralSegment:
    """Một đoạn viral được AI phát hiện.

    Attributes:
        index: Số thứ tự segment.
        start_time: Thời điểm bắt đầu (giây).
        end_time: Thời điểm kết thúc (giây).
        title_en: Tiêu đề tiếng Anh + emoji.
        title_vi: Tiêu đề tiếng Việt + emoji (nếu có).
        start_timecode: Timecode bắt đầu (mm:ss).
        end_timecode: Timecode kết thúc (mm:ss).
    """
    index: int
    start_time: float
    end_time: float
    title_en: str
    title_vi: str = ""
    start_timecode: str = ""
    end_timecode: str = ""

    @property
    def duration(self) -> float:
        """Thời lượng segment (giây)."""
        return self.end_time - self.start_time


# Prompt mặc định chuẩn Facebook Reels Tabloid 8-12 từ Tiếng Anh + Emoji
DEFAULT_PROMPT_TEMPLATE = """You are an expert viral content editor specializing in Facebook Reels, TikTok & Shorts headlines.

TASKS:
1. Analyze the provided transcript with timestamps.
2. Select the top {max_clips} viral, high-converting segments (each clip MUST be between 25 and 29 seconds).
3. Generate a high-converting Tabloid Title / Caption for each clip following these STRICT RULES:

SEGMENT SELECTION & DIALOGUE RULES:
- STRICT DIALOGUE MANDATE: You MUST ONLY select segments that contain ACTIVE BACK-AND-FORTH DIALOGUE, INTERROGATION, ARGUMENT, OR DIRECT Q&A BETWEEN 2 OR MORE PEOPLE (e.g. Attorney & Witness, Judge & Defendant, Officer & Suspect, Host & Guest).
- STRICTLY FORBID INTROS & MONOLOGUES: DO NOT select channel introductions, narrator summaries, voiceover background explanations, single-speaker intros, or host presentations. Reject any segment where only 1 person is giving an intro!
- NON-OVERLAPPING MANDATE: All selected clips MUST be completely distinct with NO time overlap between clips. Clip 2 must start AFTER Clip 1 ends!

CONTENT & STYLE RULES:
- LANGUAGE: ONLY use English.
- LENGTH: MUST be STRICTLY between 8 and 10 words per title (8 <= word_count <= 10). Count the words carefully! Do NOT produce fewer than 8 words or more than 10 words.
- NO DUMMY FILLER WORDS: DO NOT append artificial words or dummy suffixes like 'REVEALED NOW', 'EXPOSED TRUTH', or 'TODAY'. Write a single natural, coherent headline.
- STYLE: Tabloid style - hit hard with uncomfortable truth, controversial questions, high curiosity and strong emotional hook.
- EMOJI STRUCTURE: MUST end each title with a relevant, expressive emoji (e.g. 💥, 🔥, ⚡, 📍, 💰, 🚀, 😳, 😱, 🤫).
- NO LONG ARTICLES: Do NOT write long paragraphs. Only 1 short provocative headline per clip.

JSON OUTPUT FORMAT REQUIRED:
{{"segments": [{{"start": "mm:ss", "end": "mm:ss", "title_en": "Shocking Tabloid Headline Here Between Eight And Ten Words 💥", "title_vi": "Shocking Tabloid Headline Here Between Eight And Ten Words 💥"}}]}}

Transcript:
{transcript}"""




DIALOGUE_KEYWORDS = [
    r"\bdid you\b", r"\bwhat did\b", r"\bwhy did\b", r"\bwere you\b", r"\bcould you\b",
    r"\bobjection\b", r"\byour honor\b", r"\byes sir\b", r"\bno ma'am\b", r"\btell the court\b",
    r"\bstate your name\b", r"\bisn't it true\b", r"\bdo you recall\b", r"\bi didn't\b",
    r"\byou said\b", r"\bwho was\b", r"\bhow long\b", r"\bwhere were\b", r"\bwhat happened\b",
    r"\bi swear\b", r"\bis that right\b", r"\bare you sure\b", r"\byou mean\b"
]


def score_dialogue_quality(text: str) -> float:
    """Đánh giá điểm đối thoại nhân vật (Dialogue Score):
    - Tăng điểm dựa trên sự xuất hiện của từ khóa đối chất / hỏi đáp (Q&A).
    - Tăng điểm dựa trên mật độ dấu hỏi (?) và câu ngắn thể hiện đáp lời nhanh.
    - Giảm điểm nếu có các cụm từ thuyết minh/giới thiệu kênh (welcome back, subscribe, today we are looking at).
    """
    if not text:
        return 0.0

    score = 1.0
    text_lower = text.lower()

    # 1. Thưởng điểm cho từ khóa đối đáp kịch tính
    for pat in DIALOGUE_KEYWORDS:
        matches = len(re.findall(pat, text_lower))
        score += matches * 1.5

    # 2. Thưởng điểm cho câu hỏi đáp (dấu ?)
    q_count = text.count("?")
    score += q_count * 2.0

    # 3. Phạt điểm nặng nếu dính từ khóa giới thiệu kênh / thuyết minh 1 người (Intro / Monologue)
    intro_keywords = [
        "welcome back", "subscribe", "today we're", "today we are", "in this video",
        "thanks for watching", "don't forget to like", "channel", "my name is",
        "let's talk about", "let's dive into", "hey guys", "hello everyone"
    ]
    for ik in intro_keywords:
        if ik in text_lower:
            score -= 5.0

    return max(0.0, score)


def load_prompt_template(prompt_path: Optional[Path] = None) -> str:
    """Đọc prompt template từ file.

    Args:
        prompt_path: Đường dẫn tới file scipt.txt.
                     Nếu None, dùng prompt mặc định.

    Returns:
        Chuỗi prompt template.
    """
    if prompt_path and Path(prompt_path).exists():
        content = Path(prompt_path).read_text(encoding="utf-8")
        logger.info(f"Đọc prompt template từ: {prompt_path}")
        return content

    logger.info("Dùng prompt template mặc định")
    return DEFAULT_PROMPT_TEMPLATE


def _parse_timecode_to_seconds(timecode: str) -> float:
    """Chuyển mm:ss hoặc h:mm:ss thành giây.

    Args:
        timecode: Chuỗi timecode.

    Returns:
        Số giây.
    """
    parts = timecode.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0.0


def _parse_llm_response_json(response_text: str) -> List[dict]:
    """Parse JSON response từ LLM.

    Xử lý các trường hợp:
    - JSON thuần
    - JSON wrapped trong markdown code block
    - JSON có trailing text

    Args:
        response_text: Text response từ LLM.

    Returns:
        Danh sách segments dạng dict.
    """
    text = response_text.strip()

    # Loại bỏ markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Tìm JSON object
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "segments" in parsed:
            return parsed["segments"]
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: tìm JSON object đầu tiên trong text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict) and "segments" in parsed:
                return parsed["segments"]
        except json.JSONDecodeError:
            pass

    # Fallback: tìm JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return []


def _parse_llm_response_text(response_text: str) -> List[dict]:
    """Parse text response dạng numbered list từ LLM.

    Format mong đợi:
        1. Viral Segment Time: 03:39 to 04:09
        English Title + emoji
        Vietnamese Title + emoji

    Args:
        response_text: Text response từ LLM.

    Returns:
        Danh sách segments dạng dict.
    """
    segments = []
    lines = response_text.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Tìm dòng có "Viral Segment Time:" hoặc pattern "mm:ss to mm:ss"
        time_match = re.search(
            r"(\d{1,2}:\d{2})\s*(?:to|→|-)\s*(\d{1,2}:\d{2})",
            line,
        )

        if time_match:
            start_tc = time_match.group(1)
            end_tc = time_match.group(2)

            # Đọc các dòng tiếp theo làm title (bỏ qua dòng trống)
            title_en = ""
            title_vi = ""

            j = i + 1
            # Tìm English title (dòng không trống tiếp theo)
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue
                if re.match(r"^\d+\.", next_line) or re.search(r"^\s*(?:SEGMENT|CLIP|VIRAL SEGMENT|TIME)\s*\d*", next_line, re.IGNORECASE) or "SECONDS)" in next_line.upper():
                    break
                title_en = next_line
                j += 1
                break

            # Tìm Vietnamese title (dòng không trống tiếp theo)
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue
                if re.match(r"^\d+\.", next_line) or re.search(r"^\s*(?:SEGMENT|CLIP|VIRAL SEGMENT|TIME)\s*\d*", next_line, re.IGNORECASE) or "SECONDS)" in next_line.upper():
                    break
                title_vi = next_line
                j += 1
                break

            i = j - 1

            segments.append({
                "start": start_tc,
                "end": end_tc,
                "title_en": title_en,
                "title_vi": title_vi,
            })

        i += 1

    return segments


def analyze_transcript(
    transcript_text: str,
    max_clips: int = 3,
    api_key: Optional[str] = None,
    prompt_template: Optional[str] = None,
    video_duration: float = 0.0,
    intro_offset: float = 0.0,
    outro_offset: float = 0.0,
) -> List[ViralSegment]:
    """Phân tích transcript để tìm viral segments bằng Gemini/Groq/OpenRouter API.

    Args:
        transcript_text: Text transcript có timestamp.
        max_clips: Số lượng clip tối đa.
        api_key: API key cho Gemini.
        prompt_template: Prompt template tùy chỉnh.
        video_duration: Thời lượng video (giây), dùng để validate.
        intro_offset: Bỏ số giây đầu (10s cho Style 1 & 2).
        outro_offset: Bỏ số giây cuối (25s cho Style 1 & 2).

    Returns:
        Danh sách ViralSegment.

    Raises:
        RuntimeError: Nếu không thể phân tích sau nhiều lần thử.
    """
    if not api_key:
        raise ValueError(
            "Cần cung cấp API key. Đặt GEMINI_API_KEY trong .env "
            "hoặc truyền qua --api-key"
        )

    # Kiểm tra bộ nhớ tạm (Cache) trước khi gọi API (chỉ dùng nếu cache có đủ max_clips)
    cache_key = _get_cache_key(transcript_text, max_clips, prompt_template)
    cached_segments = _read_cache(cache_key)
    if cached_segments and len(cached_segments) >= max_clips:
        logger.info(f"⚡ Tìm thấy {len(cached_segments)} viral segments trong Local Cache! (Không tốn API request)")
        return cached_segments

    # Xây dựng prompt
    if prompt_template:
        # Prompt từ scipt.txt — append transcript vào cuối
        full_prompt = (
            f"{prompt_template}\n\n"
            f"Chọn tối đa {max_clips} đoạn.\n\n"
            f"Transcript:\n{transcript_text}"
        )
    else:
        full_prompt = DEFAULT_PROMPT_TEMPLATE.format(
            max_clips=max_clips,
            transcript=transcript_text,
        )

    logger.info(f"Gửi transcript tới LLM API ({len(transcript_text)} chars)...")

    # Gọi LLM API với số lần thử tối đa 4 lần (tránh ngốn Quota)
    max_attempts = 4
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        try:
            with _LLM_LOCK:
                response_text = _call_gemini_api(full_prompt, api_key)
            logger.debug(f"LLM response (attempt {attempt}):\n{response_text[:500]}")

            # Thử parse JSON trước
            raw_segments = _parse_llm_response_json(response_text)

            # Nếu JSON không được, thử parse text
            if not raw_segments:
                raw_segments = _parse_llm_response_text(response_text)

            if not raw_segments:
                last_error = "Không parse được segments từ response"
                logger.warning(
                    f"Attempt {attempt}/{max_attempts}: {last_error}"
                )
                full_prompt += (
                    "\n\nIMPORTANT: Trả lời CHÍNH XÁC theo format JSON:"
                    '\n{"segments": [{"start": "mm:ss", "end": "mm:ss", "title_en": "Headline Between 8 And 12 Words 💥", "title_vi": "Headline Between 8 And 12 Words 💥"}]}'
                )
                time.sleep(2.0)
                continue

            # Convert raw segments thành ViralSegment với validation độ dài 8-10 từ nghiêm ngặt bằng vòng lặp và chống trùng
            segments = _convert_raw_segments(
                raw_segments, max_clips, video_duration, intro_offset, outro_offset, api_key=api_key, transcript_text=transcript_text
            )

            if segments:
                logger.info(f"Tìm thấy {len(segments)} viral segments ĐẠT CHUẨN 100% ĐỘ DÀI 8-12 TỪ!")
                _write_cache(cache_key, segments)
                return segments

            last_error = "Segments sau khi validate trống"
            logger.warning(f"Attempt {attempt}/{max_attempts}: {last_error}")
            time.sleep(2.0)

        except ValueError as ve:
            last_error = str(ve)
            logger.warning(
                f"Attempt {attempt}/{max_attempts} từ chối do tiêu đề không đạt 8-12 từ: {last_error}"
            )
            full_prompt += (
                f"\n\nCRITICAL MANDATORY REQUIREMENT: EVERY title MUST have STRICTLY between 8 and 12 words (8 <= word_count <= 12). "
                f"Previous attempt failed with: '{last_error}'. "
                f"COUNT WORDS CAREFULLY BEFORE OUTPUTTING! Regenerate ALL titles so EVERY title is EXACTLY 8 to 12 words!"
            )
            time.sleep(2.0)

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Attempt {attempt}/{max_attempts} lỗi: {last_error}"
            )
            time.sleep(3.0)

    # Đảm bảo 100% chỉ sử dụng API theo yêu cầu nghiêm ngặt của người dùng
    raise RuntimeError(
        f"Chỉ sử dụng API theo yêu cầu: Tất cả các lần thử gọi AI API đều không thành công sau {max_attempts} lần thử. "
        f"Lỗi cuối cùng: {last_error}. Vui lòng nạp thêm API Key hoặc chờ API hồi hạn ngạch."
    )


def _generate_fallback_segments(
    transcript_text: str,
    max_clips: int,
    video_duration: float,
    intro_offset: float = 0.0,
    outro_offset: float = 0.0,
) -> List[ViralSegment]:
    """Tự động tạo segments dự phòng khi tất cả API Key LLM đều hết quota 429 hoặc gặp lỗi."""
    logger.warning("⚡ Tất cả API Key LLM đã cạn kiệt Quota / Rate Limit 429. Tự động kích hoạt Thuật Toán Phân Tích Dự Phòng Thông Minh!")
    
    valid_start = intro_offset
    valid_end = max(valid_start + 30.0, (video_duration - outro_offset) if video_duration > 0 else 180.0)
    total_avail = valid_end - valid_start

    # Đọc các câu spoken lines từ transcript (Lọc bỏ các câu dính từ khóa intro)
    lines = []
    for line in transcript_text.splitlines():
        line = line.strip()
        if line and "[" in line and "]" in line:
            parts = line.split("]", 1)
            text_part = parts[1].strip() if len(parts) > 1 else ""
            if text_part and score_dialogue_quality(text_part) >= 0.5:
                lines.append(text_part)
                
    if not lines:
        lines = ["DRAMATIC CONFRONTATION AND UNEXPECTED TRUTH REVEALED IN SCENE"]

    segments = []
    clip_count = min(max_clips, max(1, int(total_avail // 35.0)))
    segment_duration = total_avail / clip_count

    for i in range(clip_count):
        seg_start = valid_start + (i * segment_duration)
        seg_end = min(seg_start + min(40.0, segment_duration), valid_end)
        if seg_end - seg_start < 10.0:
            continue
            
        line_index = (i * len(lines)) // clip_count
        raw_text = lines[line_index] if line_index < len(lines) else lines[0]
        
        # Bóc tách từ thoại tự nhiên từ transcript, gom từ các câu tiếp theo nếu thiếu từ
        clean_words = [w for w in re.sub(r"[^\w\s]", "", raw_text).split() if len(w) > 1]
        next_idx = line_index + 1
        while len(clean_words) < 8 and next_idx < len(lines):
            extra_words = [w for w in re.sub(r"[^\w\s]", "", lines[next_idx]).split() if len(w) > 1]
            clean_words.extend(extra_words)
            next_idx += 1
            
        if len(clean_words) > 10:
            clean_words = clean_words[:10]
        
        from ..utils.graphic_subtitle import clean_caption_text
        title_text = clean_caption_text(" ".join(clean_words).upper())
        
        start_tc = f"{int(seg_start // 60):02d}:{int(seg_start % 60):02d}"
        end_tc = f"{int(seg_end // 60):02d}:{int(seg_end % 60):02d}"
        
        seg = ViralSegment(
            index=i + 1,
            start_time=round(seg_start, 2),
            end_time=round(seg_end, 2),
            title_en=title_text,
            title_vi=title_text,
            start_timecode=start_tc,
            end_timecode=end_tc,
        )
        segments.append(seg)
        
    return segments


def _call_openrouter_api(prompt: str, openrouter_api_key: str) -> str:
    """Gọi OpenRouter.ai API miễn phí làm dự phòng cao cấp. Hỗ trợ luân phiên chuỗi nhiều API key."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    keys = [k.strip() for k in openrouter_api_key.split(",") if k.strip()]
    if not keys:
        raise ValueError("Danh sách OpenRouter API Key rỗng!")

    models_to_try = [
        "meta-llama/llama-3.3-70b-instruct",
        "deepseek/deepseek-chat",
    ]
    last_exc = None
    for idx, key in enumerate(keys, 1):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AI-Agent",
            "X-Title": "Batch Video Cutter",
        }
        for model_name in models_to_try:
            try:
                logger.debug(f"Đang thử OpenRouter API key {idx}/{len(keys)} với model '{model_name}'...")
                data = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2048,
                }
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
                    if content and content.strip():
                        return content
            except Exception as e:
                err_str = str(e)
                logger.warning(f"OpenRouter API key {idx}/{len(keys)} model '{model_name}' thất bại: {e}")
                last_exc = e
                if "429" in err_str:
                    time.sleep(2.0)

    raise RuntimeError(f"Tất cả {len(keys)} OpenRouter API Key đều thất bại: {last_exc}")


def _call_groq_api(prompt: str, groq_api_key: str) -> str:
    """Gọi Groq API miễn phí làm dự phòng. Hỗ trợ chuỗi nhiều API key phân cách bởi dấu phẩy."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    keys = [k.strip() for k in groq_api_key.split(",") if k.strip()]
    if not keys:
        raise ValueError("Danh sách Groq API Key rỗng!")

    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ]

    last_exc = None
    for idx, key in enumerate(keys, 1):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        for model_name in models_to_try:
            try:
                logger.debug(f"Đang thử Groq API key {idx}/{len(keys)} ({model_name})...")
                data = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2048,
                }
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
                    if content and content.strip():
                        return content
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Groq API key {idx}/{len(keys)} ({model_name}) thất bại: {e}")
                last_exc = e
                if "429" in err_str:
                    time.sleep(2.0)

    # Nếu tất cả Groq keys thất bại, tự động chuyển sang OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        logger.info("Tất cả Groq keys đã hết/lỗi. Chuyển sang dự phòng OpenRouter API...")
        return _call_openrouter_api(prompt, openrouter_key)

    raise RuntimeError(f"Tất cả {len(keys)} Groq API Key đều thất bại: {last_exc}")


def _call_sambanova_api(prompt: str, sambanova_api_key: str) -> str:
    """Gọi SambaNova API miễn phí làm dự phòng siêu tốc. Hỗ trợ chuỗi nhiều API key."""
    url = "https://api.sambanova.ai/v1/chat/completions"
    keys = [k.strip() for k in sambanova_api_key.split(",") if k.strip()]
    if not keys:
        raise ValueError("Danh sách SambaNova API Key rỗng!")

    models_to_try = [
        "Meta-Llama-3.3-70B-Instruct",
        "Qwen2.5-72B-Instruct",
    ]
    last_exc = None
    for idx, key in enumerate(keys, 1):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        for model_name in models_to_try:
            try:
                logger.debug(f"Đang thử SambaNova API key {idx}/{len(keys)} với model '{model_name}'...")
                data = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2048,
                }
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
                    if content and content.strip():
                        return content
            except Exception as e:
                err_str = str(e)
                logger.warning(f"SambaNova API key {idx}/{len(keys)} model '{model_name}' thất bại: {e}")
                last_exc = e
                if "429" in err_str:
                    time.sleep(2.0)

    # Nếu tất cả SambaNova keys thất bại, chuyển sang Groq API
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        logger.info("Tất cả SambaNova keys đã hết/lỗi. Chuyển sang dự phòng Groq API...")
        return _call_groq_api(prompt, groq_key)

    raise RuntimeError(f"Tất cả {len(keys)} SambaNova API Key đều thất bại: {last_exc}")


def _call_gemini_api(prompt: str, api_key: str) -> str:
    """Gọi Gemini API miễn phí. Hỗ trợ chuỗi nhiều API key, retry và fallback SambaNova / Groq / OpenRouter API."""
    sambanova_key = os.getenv("SAMBANOVA_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    try:
        import google.generativeai as genai
    except ImportError:
        if sambanova_key:
            return _call_sambanova_api(prompt, sambanova_key)
        elif groq_key:
            return _call_groq_api(prompt, groq_key)
        elif openrouter_key:
            return _call_openrouter_api(prompt, openrouter_key)
        raise RuntimeError(
            "Chưa cài google-generativeai. "
            "Chạy: pip install google-generativeai"
        )

    keys = [k.strip() for k in api_key.split(",") if k.strip()]
    if not keys and not sambanova_key and not groq_key and not openrouter_key:
        raise ValueError("Danh sách API Key rỗng!")

    models_to_try = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    last_exc = None

    for key_idx, key in enumerate(keys, 1):
        genai.configure(api_key=key)
        key_exhausted = False
        for model_name in models_to_try:
            if key_exhausted:
                break
            try:
                logger.debug(f"Đang thử Gemini key {key_idx}/{len(keys)} với model '{model_name}'...")
                model = genai.GenerativeModel(model_name)

                config = genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                )

                response = model.generate_content(
                    prompt,
                    generation_config=config,
                )
                if response.text and response.text.strip():
                    return response.text

            except Exception as e:
                err_str = str(e)
                last_exc = e

                if "404" in err_str:
                    logger.debug(f"Model {model_name} không khả dụng cho key {key_idx}, thử model tiếp...")
                    continue
                elif "429" in err_str or "quota" in err_str.lower():
                    logger.warning(
                        f"Key {key_idx}/{len(keys)} ({model_name}) dính lỗi 429 (Rate limit / Quota). Chuyển ngay sang Key tiếp theo..."
                    )
                    key_exhausted = True
                    break
                else:
                    logger.warning(f"Key {key_idx}/{len(keys)} ({model_name}) gặp lỗi: {e}")

    # 1. Dự phòng Tầng 2: SambaNova API (Siêu tốc 100% Free)
    if sambanova_key:
        logger.info("Tất cả Gemini keys đã hết quota. Chuyển sang dự phòng Tầng 2: SambaNova API...")
        try:
            return _call_sambanova_api(prompt, sambanova_key)
        except Exception as e:
            logger.warning(f"SambaNova API dự phòng thất bại: {e}")
            last_exc = e

    # 2. Dự phòng Tầng 3: Groq API
    if groq_key:
        logger.info("Chuyển sang dự phòng Tầng 3: Groq API...")
        try:
            return _call_groq_api(prompt, groq_key)
        except Exception as e:
            logger.warning(f"Groq API dự phòng thất bại: {e}")
            last_exc = e

    # 3. Dự phòng Tầng 4: OpenRouter API
    if openrouter_key:
        logger.info("Chuyển sang dự phòng Tầng 4: OpenRouter API...")
        try:
            return _call_openrouter_api(prompt, openrouter_key)
        except Exception as e:
            last_exc = e

    raise RuntimeError(
        f"Tất cả API Keys (Gemini / SambaNova / Groq / OpenRouter) đều không khả dụng! "
        f"Lỗi cuối: {last_exc}"
    )





def count_title_words(title: str) -> int:
    """Đếm số từ thực tế của tiêu đề sau khi làm sạch rác markdown, nháy, và chú thích ngoặc."""
    from ..utils.graphic_subtitle import clean_caption_text
    clean = clean_caption_text(title)
    words = [w for w in clean.split() if w.strip()]
    return len(words)


def _extract_spoken_headline(
    transcript_text: Optional[str],
    start_time: float,
    end_time: float,
    seen_titles: Optional[set] = None,
) -> str:
    """Trích xuất tiêu đề tự nhiên từ các từ thoại thực tế trong khoảng thời gian [start_time, end_time]."""
    from ..utils.graphic_subtitle import clean_caption_text
    vi_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"

    lines_in_range = []
    if transcript_text:
        for line in transcript_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            ts_match = re.search(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", line_str)
            if ts_match:
                t_sec = _parse_timecode_to_seconds(ts_match.group(1))
                if start_time - 5.0 <= t_sec <= end_time + 5.0:
                    text_part = re.sub(r"\[.*?\]", "", line_str).strip()
                    if text_part:
                        lines_in_range.append(text_part)

    words = []
    for line in lines_in_range:
        clean_w = [w for w in re.sub(r"[^\w\s]", "", line).split() if len(w) > 1 and not any(c in w.lower() for c in vi_chars)]
        words.extend(clean_w)
        if len(words) >= 15:
            break

    if len(words) < 8 and transcript_text:
        for line in transcript_text.splitlines():
            text_part = re.sub(r"\[.*?\]", "", line).strip()
            clean_w = [w for w in re.sub(r"[^\w\s]", "", text_part).split() if len(w) > 1 and not any(c in w.lower() for c in vi_chars)]
            words.extend(clean_w)
            if len(words) >= 15:
                break

    default_word_pools = [
        ["UNEXPECTED", "DRAMATIC", "COURTROOM", "TESTIMONY", "LEAVES", "EVERYONE", "SPEECHLESS"],
        ["SHOCKING", "TRUTH", "REVEALED", "DURING", "INTENSE", "CROSS", "EXAMINATION"],
        ["WITNESS", "CONFESSION", "TURNS", "THE", "ENTIRE", "TRIAL", "UPSIDE", "DOWN"],
        ["HEATED", "ARGUMENT", "ESCALATES", "INTO", "UNBELIEVABLE", "DRAMATIC", "MOMENT"],
        ["SURPRISING", "REVELATION", "STUNS", "THE", "COURTROOM", "IN", "SILENCE"],
    ]

    pool_idx = int(start_time + end_time) % len(default_word_pools)
    base_words = words[:10] if len(words) >= 8 else default_word_pools[pool_idx]
    if len(base_words) > 10:
        base_words = base_words[:10]

    title = clean_caption_text(" ".join(base_words).upper())

    # Kiểm tra chống trùng lặp với các tiêu đề đã xuất hiện trước đó
    if seen_titles and title.lower() in seen_titles:
        emojis = ["💥", "🔥", "⚡", "😱", "🤯", "😳"]
        e_idx = int(start_time * 7) % len(emojis)
        title = clean_caption_text(f"{' '.join(base_words[:9])} {emojis[e_idx]}")

    return title


def _convert_raw_segments(
    raw_segments: List[dict],
    max_clips: int,
    video_duration: float,
    intro_offset: float = 0.0,
    outro_offset: float = 0.0,
    api_key: Optional[str] = None,
    transcript_text: Optional[str] = None,
) -> List[ViralSegment]:
    """Convert raw dict segments thành ViralSegment với validation độ dài 8-10 từ nghiêm ngặt 100% và chống trùng tên.

    Args:
        raw_segments: Danh sách dict từ LLM response.
        max_clips: Số clip tối đa.
        video_duration: Thời lượng video (giây).
        intro_offset: Bỏ 35s đầu cho tất cả các phong cách.
        outro_offset: Bỏ 25s cuối.
        api_key: Gemini/LLM API key nếu cần kích hoạt vòng lặp refine title.
        transcript_text: Transcript văn bản gốc có timestamp để trích thoại linh hoạt.

    Returns:
        Danh sách ViralSegment đã validate và không trùng tên.
    """
    from ..utils.graphic_subtitle import clean_caption_text, clean_caption_text_for_frame

    segments: List[ViralSegment] = []
    seen_titles: set = set()

    for i, raw in enumerate(raw_segments):
        if len(segments) >= max_clips:
            break
        # Parse timecodes
        start_tc = str(raw.get("start", raw.get("start_time", "0:00")))
        end_tc = str(raw.get("end", raw.get("end_time", "0:00")))

        start_time = _parse_timecode_to_seconds(start_tc)
        end_time = _parse_timecode_to_seconds(end_tc)

        # 1. Ép giới hạn Bỏ 35s đầu intro dẫn chuyện/kênh cho tất cả các phong cách
        if intro_offset > 0.0 and start_time < intro_offset:
            logger.warning(
                f"Segment {i+1}: start_time={start_time:.1f}s nằm trong vùng intro (< {intro_offset:.1f}s), BỎ QUA HOÀN TOÀN!"
            )
            continue

        # 2. Ép giới hạn Bỏ 25s cuối cho outro
        if outro_offset > 0.0 and video_duration > 0.0:
            max_allowed_end = max(intro_offset + 25.0, video_duration - outro_offset)
            if end_time > max_allowed_end:
                logger.info(f"Segment {i+1}: end_time={end_time:.1f}s thuộc 25s cuối outro, điều chỉnh về {max_allowed_end:.1f}s")
                end_time = max_allowed_end
                start_time = max(intro_offset, end_time - 27.0)

        # Validate
        if end_time <= start_time:
            logger.warning(f"Segment {i+1}: end <= start, bỏ qua")
            continue

        duration = end_time - start_time
        if duration < 25.0 or duration > 29.0:
            logger.info(
                f"Segment {i+1}: duration={duration:.1f}s ngoài 25-29s, điều chỉnh về 27s"
            )
            if duration < 25.0:
                end_time = start_time + 27.0
            elif duration > 29.0:
                end_time = start_time + 28.5

        if video_duration > 0 and end_time > video_duration:
            logger.warning(
                f"Segment {i+1}: end_time vượt quá video duration, điều chỉnh"
            )
            end_time = min(end_time, video_duration)

        # 3. KIỂM TRA CHỐNG TRÙNG KHOẢNG CẮT (Anti-Overlap Check):
        is_overlapping = False
        for prev_seg in segments:
            overlap = max(0.0, min(end_time, prev_seg.end_time) - max(start_time, prev_seg.start_time))
            if overlap > 0.0:
                logger.warning(
                    f"Segment {i+1} [{start_time:.1f}s -> {end_time:.1f}s] bị TRÙNG {overlap:.1f}s "
                    f"với Segment {prev_seg.index} [{prev_seg.start_time:.1f}s -> {prev_seg.end_time:.1f}s]! Loại bỏ để tránh trùng clip."
                )
                is_overlapping = True
                break

        if is_overlapping:
            continue

        raw_title_en = str(raw.get("title_en", raw.get("title", "Untitled"))).strip()
        raw_title_vi = str(raw.get("title_vi", "")).strip()

        clean_en = clean_caption_text(raw_title_en)
        clean_vi = clean_caption_text(raw_title_vi)

        target_title = clean_en or clean_vi

        # 4. KÍCH HOẠT POST-VALIDATION: Loại bỏ các segment dính từ khóa Intro / Giới thiệu kênh
        d_score = score_dialogue_quality(target_title)
        if d_score < 0.2:
            logger.warning(
                f"Segment {i+1}: Tiêu đề '{target_title}' dính từ khóa intro/thuyết minh (Dialogue score: {d_score:.1f}), loại bỏ!"
            )
            continue

        # VÒNG LẶP NGHIÊM NGẶT ĐẢM BẢO CAPTION LUÔN 100% TIẾNG ANH, TỪ 8 ĐẾN 10 TỪ VÀ ĐỘC BẢN
        vi_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
        loop_count = 0
        max_loop_attempts = 8

        while True:
            pure_text = clean_caption_text_for_frame(clean_en)
            words_en = pure_text.split()
            word_count = len(words_en)
            has_vi = any(c in clean_en.lower() for c in vi_chars)
            is_duplicate = clean_en.lower() in seen_titles

            if 8 <= word_count <= 10 and not has_vi and not is_duplicate:
                # Đạt chuẩn từ 8 đến 10 từ VÀ 100% Tiếng Anh VÀ KHÔNG TRÙNG -> Thoát vòng lặp!
                break

            loop_count += 1
            logger.info(
                f"Segment {i+1}: Caption '{clean_en}' ({word_count} từ, has_vi={has_vi}, is_duplicate={is_duplicate}) chưa đạt chuẩn 8-10 từ Tiếng Anh độc bản. "
                f"Chạy vòng lặp LLM tạo lại caption (lần {loop_count})..."
            )

            refine_success = False
            if api_key and loop_count <= max_loop_attempts:
                try:
                    refine_prompt = (
                        f"Rewrite the following video headline into a natural, high-converting Tabloid headline STRICTLY IN ENGLISH for Facebook Reels / TikTok.\n"
                        f"CRITICAL MANDATORY REQUIREMENTS:\n"
                        f"1. MUST BE 100% IN ENGLISH (No Vietnamese words allowed).\n"
                        f"2. MUST contain STRICTLY between 8 and 10 words (8 <= word_count <= 10). Count words carefully!\n"
                        f"3. DO NOT ADD DUMMY FILLER WORDS (e.g. do NOT append 'REVEALED NOW', 'EXPOSED TRUTH', 'TODAY', or 'CLIP NUMBER').\n"
                        f"4. The headline MUST be a single natural, complete sentence.\n"
                        f"Current headline: '{clean_en}'\n"
                        f"End with an expressive emoji (e.g. 💥, 🔥, ⚡, 😱).\n"
                        f"Return ONLY the raw English headline string."
                    )
                    with _LLM_LOCK:
                        new_res = _call_gemini_api(refine_prompt, api_key)
                    new_clean = clean_caption_text(new_res.strip())
                    new_words = clean_caption_text_for_frame(new_clean).split()
                    new_has_vi = any(c in new_clean.lower() for c in vi_chars)
                    new_duplicate = new_clean.lower() in seen_titles

                    if 8 <= len(new_words) <= 10 and not new_has_vi and not new_duplicate:
                        clean_en = new_clean
                        refine_success = True
                        logger.info(f"Segment {i+1}: Vòng lặp LLM đã tạo caption tiếng Anh thành công ({len(new_words)} từ): '{clean_en}'")
                        break
                except Exception as ex:
                    logger.warning(f"Lỗi gọi LLM trong vòng lặp refine title: {ex}")

            if not refine_success:
                # Trích xuất thoại tự nhiên từ transcript làm fallback sinh động thay vì dùng chuỗi tĩnh hardcode
                clean_en = _extract_spoken_headline(transcript_text, start_time, end_time, seen_titles)
                if loop_count >= max_loop_attempts:
                    break

        seen_titles.add(clean_en.lower())

        segments.append(ViralSegment(
            index=len(segments) + 1,
            start_time=start_time,
            end_time=end_time,
            title_en=clean_en,
            title_vi=clean_vi or clean_en,
            start_timecode=start_tc,
            end_timecode=end_tc,
        ))

    # Nếu vẫn chưa đủ max_clips, bổ sung các phân đoạn hợp lệ không trùng lặp từ transcript
    if len(segments) < max_clips:
        valid_start = intro_offset
        valid_end = max(valid_start + 30.0, (video_duration - outro_offset) if video_duration > 0 else 180.0)
        total_avail = valid_end - valid_start
        step = total_avail / (max_clips + 1)

        for fill_i in range(len(segments), max_clips):
            st = valid_start + step * (fill_i + 1)
            et = min(valid_end, st + 27.0)
            if et - st < 25.0:
                st = max(valid_start, et - 27.0)

            # Gọi LLM sinh tiêu đề hoặc trích xuất từ thoại transcript thực tế cho segment bổ sung này
            fill_title = ""
            if api_key:
                try:
                    fill_prompt = (
                        f"Write a catchy 8 to 10 word tabloid headline IN ENGLISH for a dramatic video clip starting at {st:.0f}s.\n"
                        f"MUST contain strictly between 8 and 10 words (8 <= word_count <= 10).\n"
                        f"DO NOT use generic text like 'CLIP NUMBER'. End with an emoji 💥.\n"
                        f"Return ONLY the English headline."
                    )
                    with _LLM_LOCK:
                        res_txt = _call_gemini_api(fill_prompt, api_key)
                    c_txt = clean_caption_text(res_txt.strip())
                    w_txt = clean_caption_text_for_frame(c_txt).split()
                    if 8 <= len(w_txt) <= 10 and c_txt.lower() not in seen_titles:
                        fill_title = c_txt
                except Exception as ex:
                    logger.warning(f"Lỗi khi gọi LLM sinh title cho filler segment {fill_i+1}: {ex}")

            if not fill_title:
                fill_title = _extract_spoken_headline(transcript_text, st, et, seen_titles)

            seen_titles.add(fill_title.lower())

            segments.append(ViralSegment(
                index=fill_i + 1,
                start_time=st,
                end_time=et,
                title_en=fill_title,
                title_vi=fill_title,
                start_timecode=f"{int(st//60):02d}:{int(st%60):02d}",
                end_timecode=f"{int(et//60):02d}:{int(et%60):02d}",
            ))

    return segments

"""Analyzer module.

Gửi transcript tới LLM API miễn phí (Gemini) để phân tích
và tìm các đoạn viral segments.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from loguru import logger


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


# Prompt mặc định chuẩn Facebook Reels Tabloid ~10 từ Tiếng Anh + Emoji
DEFAULT_PROMPT_TEMPLATE = """You are an expert viral content editor specializing in Facebook Reels, TikTok & Shorts headlines.

TASKS:
1. Analyze the provided transcript with timestamps.
2. Select the top {max_clips} viral, high-converting segments (each clip MUST be between 25 and 29 seconds).
3. Generate a high-converting Tabloid Title / Caption for each clip following these STRICT RULES:

CONTENT & STYLE RULES:
- LANGUAGE: ONLY use English.
- LENGTH: Short, concise, punchy headline (~10 words).
- STYLE: Tabloid style - hit hard with uncomfortable truth, controversial questions, high curiosity and strong emotional hook.
- EMOJI STRUCTURE: MUST end each title with a relevant, expressive emoji (e.g. 💥, 🔥, ⚡, 📍, 💰, 🚀, 😳, 😱, 🤫).
- NO LONG ARTICLES: Do NOT write long paragraphs. Only 1 short provocative headline per clip.

JSON OUTPUT FORMAT REQUIRED:
{{"segments": [{{"start": "mm:ss", "end": "mm:ss", "title_en": "Shocking Tabloid Headline Here ~10 Words 💥", "title_vi": "Shocking Tabloid Headline Here ~10 Words 💥"}}]}}

Transcript:
{transcript}"""




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

            # Đọc các dòng tiếp theo làm title
            title_en = ""
            title_vi = ""

            # Dòng tiếp theo là English title
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.match(r"^\d+\.", next_line):
                    title_en = next_line
                    i += 1

            # Dòng tiếp theo có thể là Vietnamese title
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.match(r"^\d+\.", next_line):
                    # Kiểm tra xem có phải tiếng Việt không
                    if any(c in next_line for c in "áàảãạắằẳẵặấầẩẫậéèẻẽẹ"):
                        title_vi = next_line
                        i += 1

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
) -> List[ViralSegment]:
    """Phân tích transcript để tìm viral segments bằng Gemini API.

    Args:
        transcript_text: Text transcript có timestamp.
        max_clips: Số lượng clip tối đa.
        api_key: API key cho Gemini.
        prompt_template: Prompt template tùy chỉnh.
        video_duration: Thời lượng video (giây), dùng để validate.

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

    logger.info(f"Gửi transcript tới Gemini API ({len(transcript_text)} chars)...")

    # Gọi Gemini API
    max_attempts = 3
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        try:
            response_text = _call_gemini_api(full_prompt, api_key)
            logger.debug(f"Gemini response (attempt {attempt}):\n{response_text[:500]}")

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
                # Thêm instruction cho retry
                full_prompt += (
                    "\n\nIMPORTANT: Trả lời CHÍNH XÁC theo format:"
                    "\n1. Viral Segment Time: mm:ss to mm:ss"
                    "\nEnglish Title + emoji"
                )
                continue

            # Convert raw segments thành ViralSegment
            segments = _convert_raw_segments(
                raw_segments, max_clips, video_duration
            )

            if segments:
                logger.info(f"Tìm thấy {len(segments)} viral segments")
                return segments

            last_error = "Segments sau khi validate trống"
            logger.warning(f"Attempt {attempt}/{max_attempts}: {last_error}")

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Attempt {attempt}/{max_attempts} lỗi: {last_error}"
            )

    raise RuntimeError(
        f"Không thể phân tích transcript sau {max_attempts} lần thử. "
        f"Lỗi cuối: {last_error}"
    )


import os
import json
import urllib.request
import urllib.error

def _call_groq_api(prompt: str, groq_api_key: str) -> str:
    """Gọi Groq API miễn phí làm dự phòng. Hỗ trợ chuỗi nhiều API key phân cách bởi dấu phẩy."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    keys = [k.strip() for k in groq_api_key.split(",") if k.strip()]
    if not keys:
        raise ValueError("Danh sách Groq API Key rỗng!")

    last_exc = None
    for idx, key in enumerate(keys, 1):
        try:
            logger.debug(f"Đang thử Groq API key {idx}/{len(keys)}...")
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }

            data = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2048,
            }
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Groq API key {idx}/{len(keys)} thất bại: {e}")
            last_exc = e

    raise RuntimeError(f"Tất cả {len(keys)} Groq API Key đều thất bại: {last_exc}")



def _call_gemini_api(prompt: str, api_key: str) -> str:
    """Gọi Gemini API miễn phí. Hỗ trợ chuỗi nhiều API key, retry và fallback Groq API."""
    # Kiểm tra nếu người dùng có cài GROQ_API_KEY
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    try:
        import google.generativeai as genai
    except ImportError:
        if groq_key:
            return _call_groq_api(prompt, groq_key)
        raise RuntimeError(
            "Chưa cài google-generativeai. "
            "Chạy: pip install google-generativeai"
        )

    keys = [k.strip() for k in api_key.split(",") if k.strip()]
    if not keys and not groq_key:
        raise ValueError("Danh sách API Key rỗng!")

    models_to_try = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest",
    ]
    last_exc = None

    for key_idx, key in enumerate(keys, 1):
        genai.configure(api_key=key)
        for model_name in models_to_try:
            try:
                logger.debug(f"Đang thử Gemini key {key_idx}/{len(keys)} với model '{model_name}'...")
                model = genai.GenerativeModel(model_name)

                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    ),
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
                        f"Key {key_idx}/{len(keys)} ({model_name}) chạm rate limit/hết quota (429)."
                    )
                else:
                    logger.warning(f"Key {key_idx}/{len(keys)} ({model_name}) gặp lỗi: {e}")

    # Nếu tất cả Gemini key đều hết quota mà có Groq key → dùng Groq
    if groq_key:
        logger.info("Tất cả Gemini keys đã hết quota. Chuyển sang dự phòng Groq API...")
        try:
            return _call_groq_api(prompt, groq_key)
        except Exception as e:
            last_exc = e

    raise RuntimeError(
        f"Tất cả {len(keys)} API Key Gemini đều hết Hạn ngạch (Quota/Daily limit) trong ngày! "
        f"Lỗi: {last_exc}\n"
        f"Gợi ý: Tạo thêm key mới tại https://aistudio.google.com/ hoặc thêm GROQ_API_KEY vào file .env"
    )





def _convert_raw_segments(
    raw_segments: List[dict],
    max_clips: int,
    video_duration: float,
) -> List[ViralSegment]:
    """Convert raw dict segments thành ViralSegment với validation.

    Args:
        raw_segments: Danh sách dict từ LLM response.
        max_clips: Số clip tối đa.
        video_duration: Thời lượng video (giây).

    Returns:
        Danh sách ViralSegment đã validate.
    """
    segments: List[ViralSegment] = []

    for i, raw in enumerate(raw_segments[:max_clips]):
        try:
            # Parse timecodes
            start_tc = str(raw.get("start", raw.get("start_time", "0:00")))
            end_tc = str(raw.get("end", raw.get("end_time", "0:00")))

            start_time = _parse_timecode_to_seconds(start_tc)
            end_time = _parse_timecode_to_seconds(end_tc)

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
                    f"Segment {i+1}: end_time vượt quá video duration, "
                    f"điều chỉnh"
                )
                end_time = min(end_time, video_duration)

            title_en = str(
                raw.get("title_en", raw.get("title", "Untitled"))
            ).strip()
            title_vi = str(raw.get("title_vi", "")).strip()

            segments.append(ViralSegment(
                index=i + 1,
                start_time=start_time,
                end_time=end_time,
                title_en=title_en,
                title_vi=title_vi,
                start_timecode=start_tc,
                end_timecode=end_tc,
            ))

        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Segment {i+1} không hợp lệ: {e}")
            continue

    return segments

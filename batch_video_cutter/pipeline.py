"""Main processing pipeline orchestrator.

Handles batch processing of videos with max_workers=2 concurrency,
progress tracking, output directory management, caption summary generation,
and error handling.
"""

import asyncio
import datetime
import functools
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from tqdm import tqdm

from .config import AppConfig
from .core.scanner import scan_videos, VideoInfo
from .core.transcriber import transcribe_video, format_transcript_for_llm, cleanup_whisper_model
from .core.analyzer import analyze_transcript, load_prompt_template, ViralSegment
from .core.engine import cut_and_render_clip
from .styles.factory import parse_style_mapping, resolve_style_for_folder
from .utils.subtitle import create_subtitles_from_transcript
from .utils.ffmpeg_check import check_ffmpeg
import sys


from .utils.asset_downloader import download_all_assets
from .utils.emoji_manager import copy_cache_to_assets, get_emoji_png_path, extract_emoji_from_text



class PipelineOrchestrator:

    """Orchestrates the entire batch video cutting workflow."""


    def __init__(self, config: AppConfig):
        self.config = config
        self.style_mapping = parse_style_mapping(config.style_mapping_str)
        self.prompt_template = load_prompt_template(config.prompt_template_path)

        # Thư mục Output gốc (ví dụ: C:\Users\Admin\Desktop\output\final_clips)
        base_dir = config.output_dir if config.output_dir else (config.input_dir / "final_clips")

        # Đóng gói video thành phẩm theo folder phiên làm việc chuẩn 100% giống Phong cách 1 & 2
        if config.session_folder_name:
            folder_name = config.session_folder_name.replace("/", "_").replace("\\", "_")
        else:
            now = datetime.datetime.now()
            folder_name = f"batch_export_{now.strftime('%Y%m%d_%H%M%S')}"

        self.bundle_dir = base_dir / folder_name
        self.bundle_dir.mkdir(parents=True, exist_ok=True)


        self.state_file = self.bundle_dir / "pipeline_state.json"
        self.completed_videos, self.saved_results_list = self._load_state()
        if self.saved_results_list:
            self._write_captions_summary(self.saved_results_list)


    def _load_state(self) -> tuple:
        """Tải trạng thái video đã hoàn thành và kết quả clip để resume."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                completed = set(data.get("completed_videos", []))
                results = data.get("results_list", [])
                return completed, results
            except Exception as e:
                logger.warning(f"Không thể đọc file state: {e}")
        return set(), []

    def _save_state(self, video_path: str, new_results: list = None):
        """Lưu trạng thái video hoàn thành và tự động cập nhật ngay file all_clip_titles.txt."""
        self.completed_videos.add(video_path)
        if new_results:
            new_filenames = {r["filename"] for r in new_results}
            self.saved_results_list = [r for r in self.saved_results_list if r["filename"] not in new_filenames]
            self.saved_results_list.extend(new_results)

        try:
            self.state_file.write_text(
                json.dumps({
                    "completed_videos": list(self.completed_videos),
                    "results_list": self.saved_results_list,
                }, indent=2),
                encoding="utf-8"
            )
            self._write_captions_summary(self.saved_results_list)
        except Exception as e:
            logger.warning(f"Không thể ghi file state: {e}")

    async def process_single_video(
        self,
        video_info: VideoInfo,
        semaphore: asyncio.Semaphore,
        transcribe_semaphore: asyncio.Semaphore,
        progress_bar: tqdm,
        results_list: list,
    ):
        """Xử lý 1 video duy nhất với semaphore giới hạn concurrency."""
        async with semaphore:
            str_path = str(video_info.path)
            first_clip_path = self.bundle_dir / f"{video_info.folder_name}.1.mp4"
            if str_path in self.completed_videos and first_clip_path.exists():
                logger.info(f"Đã xử lý trước đó và file clip tồn tại, bỏ qua: {video_info.path.name}")
                progress_bar.update(1)
                return

            logger.info(f"--- Bắt đầu xử lý: Folder [{video_info.folder_name}] | {video_info.path.name} ---")


            try:
                # 1. Transcribe bằng Whisper (dùng transcribe_semaphore tuần tự 1 video/lần trên CPU)
                async with transcribe_semaphore:
                    loop = asyncio.get_running_loop()
                    transcript = await loop.run_in_executor(
                        None,
                        transcribe_video,
                        video_info.path,
                        self.config.whisper_model,
                    )

                if not transcript.segments:
                    logger.warning(f"Không lấy được transcript cho {video_info.path.name}")
                    progress_bar.update(1)
                    return

                # 2. Phân tích viral segments qua LLM API
                transcript_text = format_transcript_for_llm(transcript)
                segments: List[ViralSegment] = await loop.run_in_executor(
                    None,
                    analyze_transcript,
                    transcript_text,
                    self.config.max_clips_per_video,
                    self.config.gemini_api_key,
                    self.prompt_template,
                    transcript.duration,
                )

                if not segments:
                    logger.warning(f"Không tìm thấy đoạn viral cho {video_info.path.name}")
                    progress_bar.update(1)
                    return

                # 3. Xác định phong cách render theo folder index
                style = resolve_style_for_folder(video_info.folder_index, self.style_mapping)
                logger.info(f"Sử dụng {style.name} cho folder [{video_info.folder_name}]")

                video_results = []
                # 4. Render từng clip
                for clip_idx, seg in enumerate(segments, 1):
                    # Tên video chuẩn dạng giống Phong cách 1 & 2: 25.1.mp4, 25.2.mp4, 25.3.mp4
                    clip_filename = f"{video_info.folder_name}.{clip_idx}.mp4"
                    output_clip_path = self.bundle_dir / clip_filename


                    with tempfile.TemporaryDirectory() as tmp_dir:
                        sub_path = Path(tmp_dir) / f"sub_{clip_idx}.ass"
                        sub_position = style.get_subtitle_position()

                        # Tạo subtitles chuẩn theo style với độ phân giải canvas chuẩn xác
                        sub_path, timed_emojis = await loop.run_in_executor(
                            None,
                            functools.partial(
                                create_subtitles_from_transcript,
                                segments=transcript.segments,
                                clip_start=seg.start_time,
                                clip_end=seg.end_time,
                                output_path=sub_path,
                                position=sub_position,
                                font_name=getattr(style, "get_font_name", lambda: "Montserrat Black")(),
                                font_size=getattr(style, "get_font_size", lambda: 85)(),
                                highlight_color_name=getattr(style, "get_highlight_color", lambda: "green")(),
                                italic=getattr(style, "get_italic_option", lambda: False)(),
                                add_emojis=True,
                                canvas_size=style.get_output_resolution(),
                            )
                        )

                        # Đảm bảo 100% video Style 3 & Style 4 đều có Top Caption (nếu thiếu title_en/vi thì tự lấy reason hoặc text thoại để chạy vòng lặp 8-12 từ)
                        title_text = seg.title_en or seg.title_vi or getattr(seg, "reason", "") or seg.text
                        if getattr(style, "get_caption_area", lambda: None)():
                            from batch_video_cutter.utils.graphic_subtitle import generate_top_caption_layer
                            top_cap_png = Path(tmp_dir) / f"top_caption_{clip_idx}.png"
                            canvas_res = style.get_output_resolution()
                            top_area_h = 180 if canvas_res[1] == 1080 else 280
                            cap_png_path = generate_top_caption_layer(
                                title_text,
                                output_png=top_cap_png,
                                canvas_size=canvas_res,
                                top_area_height=top_area_h,
                                fallback_text=getattr(seg, "text", ""),
                            )
                            if cap_png_path and cap_png_path.exists():
                                clip_dur = seg.end_time - seg.start_time
                                timed_emojis = [(cap_png_path, 0.0, clip_dur)] + (timed_emojis or [])

                        # Render clip bằng FFmpeg với Dynamic Timed HD Color Emoji PNG & Top Caption Badge PNG
                        await loop.run_in_executor(
                            None,
                            functools.partial(
                                cut_and_render_clip,
                                video_path=video_info.path,
                                start_time=seg.start_time,
                                end_time=seg.end_time,
                                output_path=output_clip_path,
                                style=style,
                                subtitle_path=sub_path,
                                timed_emojis=timed_emojis,
                                title_text=title_text,
                            )
                        )


                    # Lưu thông tin cho file tiêu đề
                    item_info = {
                        "filename": clip_filename,
                        "title": seg.title_en or seg.title_vi,
                        "folder_name": video_info.folder_name,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "reason": getattr(seg, "reason", ""),
                    }
                    video_results.append(item_info)
                    results_list.append(item_info)

                self._save_state(str_path, video_results)
                logger.info(f"Hoàn tất video: {video_info.path.name}")

            except Exception as e:
                logger.error(f"Lỗi khi xử lý video {video_info.path.name}: {e}")

            finally:
                progress_bar.update(1)

    async def run_async(self):
        """Khởi chạy toàn bộ pipeline batch."""
        check_ffmpeg()
        download_all_assets()
        copy_cache_to_assets()

        logger.info(f"Quét video trong: {self.config.input_dir}")


        videos = scan_videos(self.config.input_dir)

        if not videos:
            logger.error("Không tìm thấy video .mp4 nào để xử lý.")
            return

        semaphore = asyncio.Semaphore(self.config.max_workers)
        transcribe_semaphore = asyncio.Semaphore(1)  # Giới hạn 1 video transcribe trên CPU tại 1 thời điểm
        results_list: list = []

        logger.info(f"Bắt đầu xử lý {len(videos)} video (Concurrency: {self.config.max_workers}, Transcribe CPU: 1)...")

        # Điều hướng loguru sink qua tqdm.write để không bị đè chữ trên console
        logger.remove()
        logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)

        try:
            with tqdm(total=len(videos), desc="Tiến độ tổng") as pbar:
                tasks = [
                    self.process_single_video(v, semaphore, transcribe_semaphore, pbar, results_list)
                    for v in videos
                ]
                await asyncio.gather(*tasks)

            # 5. Xuất các file tổng hợp tiêu đề vào DUY NHẤT thư mục đóng gói self.bundle_dir
            self._write_captions_summary(results_list)
            logger.info(f"==== TẤT CẢ HOÀN TẤT! Tất cả video clip & file txt đã đóng gói tại: {self.bundle_dir} ====")
        finally:
            cleanup_whisper_model()

    def _write_captions_summary(self, results_list: list):
        """Ghi duy nhất 1 file all_clip_titles.txt tổng hợp tiêu đề và caption rõ ràng, không trùng lặp."""
        self.bundle_dir.mkdir(parents=True, exist_ok=True)
        results_list.sort(key=lambda x: x["filename"])

        # Xóa các file txt thừa cũ nếu có để đảm bảo CHỈ CÓ 1 FILE DUY NHẤT
        for old_file in ["danh_sach_tieu_de.txt", "captions.txt"]:
            old_path = self.bundle_dir / old_file
            if old_path.exists():
                try:
                    old_path.unlink()
                except Exception as e:
                    logger.warning(f"Không thể xóa file cũ {old_file}: {e}")

        # Ghi DUY NHẤT 1 file: all_clip_titles.txt
        all_titles_path = self.bundle_dir / "all_clip_titles.txt"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "=" * 80,
            "                   BÁO CÁO TỔNG HỢP CLIP & TIÊU ĐỀ SHORT/REELS",
            f"Thời gian tạo : {now_str}",
            f"Thư mục xuất  : {self.bundle_dir}",
            f"Tổng số clips : {len(results_list)} clips",
            "=" * 80,
            "",
        ]

        for stt, item in enumerate(results_list, 1):
            lines.append(f"[{item['filename']}]")
            lines.append(f"File Output       : {item['filename']}")
            lines.append(f"Tiêu Đề / Caption  : {item['title']}")
            lines.append(f"Folder Video Gốc  : {item['folder_name']}")
            lines.append(f"Timestamp Đoạn Cắt : {item['start_time']:.1f}s -> {item['end_time']:.1f}s")
            if item.get("reason"):
                lines.append(f"Lý Do Chọn Clip   : {item['reason']}")
            lines.append("-" * 80)

        all_titles_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Đã ghi file tổng hợp duy nhất: {all_titles_path}")





    def run(self):
        """Entry point đồng bộ cho CLI."""
        asyncio.run(self.run_async())

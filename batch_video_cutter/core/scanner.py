"""Scanner module.

Quét đệ quy folder nguồn → tìm tất cả file .mp4.
Cấu trúc folder: {folder_name}/{date}/{video_id}/*.mp4
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from loguru import logger


@dataclass
class VideoInfo:
    """Thông tin về một video nguồn được tìm thấy.

    Attributes:
        path: Đường dẫn tuyệt đối tới file .mp4.
        folder_name: Tên folder gốc (ví dụ: "1", "2").
        folder_index: Số thứ tự folder (dùng cho style mapping).
        video_id: ID video (tên folder chứa file video).
    """
    path: Path
    folder_name: str
    folder_index: int
    video_id: str


def _extract_folder_index(folder_name: str) -> int:
    """Trích xuất số thứ tự từ tên folder.

    Thử parse số từ tên folder. Nếu không phải số thuần,
    dùng regex trích xuất số đầu tiên tìm thấy (ví dụ: 'folder_12' -> 12).
    Nếu không có số nào, mới dùng hash để tạo index duy nhất.

    Args:
        folder_name: Tên folder gốc.

    Returns:
        Số thứ tự (int).
    """
    try:
        return int(folder_name)
    except ValueError:
        match = re.search(r"\d+", folder_name)
        if match:
            return int(match.group())
        return abs(hash(folder_name)) % 10000


def scan_videos(input_dir: Path) -> List[VideoInfo]:
    """Quét đệ quy folder nguồn để tìm tất cả file .mp4.

    Cấu trúc mong đợi:
        input_dir/
            {folder_name}/          ← folder gốc (ví dụ: "1", "2")
                {date}/             ← subfolder ngày
                    {video_id}/     ← subfolder video ID
                        *.mp4       ← file video

    Args:
        input_dir: Đường dẫn folder gốc chứa các folder video.

    Returns:
        Danh sách VideoInfo, sắp xếp theo folder_index.

    Raises:
        FileNotFoundError: Nếu input_dir không tồn tại.
    """
    input_dir = Path(input_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Folder nguồn không tồn tại: {input_dir}")

    if not input_dir.is_dir():
        raise NotADirectoryError(f"Không phải folder: {input_dir}")

    videos: List[VideoInfo] = []

    # Duyệt các folder con trực tiếp (folder_name: "1", "2", ...)
    for folder_entry in sorted(input_dir.iterdir()):
        if not folder_entry.is_dir():
            continue

        folder_name = folder_entry.name

        # Bỏ qua các folder ẩn, hệ thống và folder output
        if folder_name.startswith(".") or folder_name.startswith("_") or folder_name.lower() in ("final_clips", "output"):
            continue

        # Tìm tất cả file video đệ quy trong folder này (.mp4, .webm, .mkv, .mov, .avi)
        video_extensions = ("*.mp4", "*.webm", "*.mkv", "*.mov", "*.avi")
        video_files = []
        for ext in video_extensions:
            video_files.extend(list(folder_entry.rglob(ext)))

        if not video_files:
            logger.warning(f"Không tìm thấy file video trong folder: {folder_entry}")
            continue

        folder_index = _extract_folder_index(folder_name)

        for video_file in video_files:
            # Xác định video_id từ folder cha chứa file video
            video_id = video_file.parent.name

            video_info = VideoInfo(
                path=video_file.resolve(),
                folder_name=folder_name,
                folder_index=folder_index,
                video_id=video_id,
            )
            videos.append(video_info)
            logger.debug(
                f"Tìm thấy video: folder={folder_name} "
                f"id={video_id} path={video_file.name}"
            )

    # Sắp xếp theo folder_index
    videos.sort(key=lambda v: (v.folder_index, v.path.name))


    logger.info(f"Tổng cộng tìm thấy {len(videos)} video trong {input_dir}")
    return videos


def scan_single_folder(folder_path: Path) -> List[VideoInfo]:
    """Quét một folder đơn (không phải cấu trúc lồng nhau).

    Dùng khi input_dir chính là folder chứa video trực tiếp.

    Args:
        folder_path: Đường dẫn folder chứa video.

    Returns:
        Danh sách VideoInfo.
    """
    folder_path = Path(folder_path)

    if not folder_path.exists():
        raise FileNotFoundError(f"Folder không tồn tại: {folder_path}")

    videos: List[VideoInfo] = []
    folder_name = folder_path.name
    folder_index = _extract_folder_index(folder_name)

    video_extensions = ("*.mp4", "*.webm", "*.mkv", "*.mov", "*.avi")
    for ext in video_extensions:
        for video_file in folder_path.rglob(ext):
            video_info = VideoInfo(
                path=video_file.resolve(),
                folder_name=folder_name,
                folder_index=folder_index,
                video_id=video_file.stem,
            )
            videos.append(video_info)

    videos.sort(key=lambda v: v.path.name)
    return videos


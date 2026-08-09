import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from batch_video_cutter.config import AppConfig
from batch_video_cutter.pipeline import PipelineOrchestrator

@pytest.mark.asyncio
async def test_parallel_clip_rendering(tmp_path):
    config = AppConfig(
        input_dir=tmp_path,
        output_dir=tmp_path / "output",
        max_render_workers=4
    )
    orchestrator = PipelineOrchestrator(config)
    assert hasattr(orchestrator, "render_semaphore")
    assert orchestrator.render_semaphore._value == 4

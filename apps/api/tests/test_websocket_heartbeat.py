"""
Unit tests for WebSocket heartbeat functionality (Step 1.2)

Tests the send_periodic_heartbeat() function that prevents
WebSocket disconnections during long document generations.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document import AIGenerationJob
from app.services.background_jobs import send_periodic_heartbeat


class TestWebSocketHeartbeat:
    """Test WebSocket heartbeat functionality"""

    @pytest.mark.asyncio
    async def test_heartbeat_sends_messages_periodically(self):
        """Test that heartbeat sends WebSocket messages at correct interval"""
        # Mock WebSocket manager
        mock_manager = AsyncMock()

        # Mock database session
        mock_db = AsyncMock()
        mock_job = AIGenerationJob(id=1, document_id=100, status="running", progress=0)

        # Setup mock to return running job 3 times, then completed
        call_count = 0

        async def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            # Create mock result
            mock_result = MagicMock()
            if call_count <= 3:
                # Job still running
                mock_job.status = "running"
                mock_result.scalar_one_or_none.return_value = mock_job
            else:
                # Job completed
                mock_job.status = "completed"
                mock_result.scalar_one_or_none.return_value = mock_job

            return mock_result

        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # Patch dependencies
        with patch(
            "app.services.background_jobs.database.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock()
            ),
        ):
            with patch("app.services.background_jobs.manager", mock_manager):
                # Run heartbeat with short interval
                await send_periodic_heartbeat(
                    user_id=1,
                    job_id=1,
                    document_id=100,
                    interval=0.1,  # 100ms for fast test
                )

        # Verify heartbeat was sent 3 times (stopped when job completed)
        assert mock_manager.send_progress.call_count == 3

        # Verify message structure
        first_call = mock_manager.send_progress.call_args_list[0]
        assert first_call[0][0] == 1  # user_id
        message = first_call[0][1]
        assert message["type"] == "heartbeat"
        assert message["job_id"] == 1
        assert message["document_id"] == 100
        assert "timestamp" in message

    @pytest.mark.asyncio
    async def test_heartbeat_stops_when_job_fails(self):
        """Test that heartbeat stops when job status becomes 'failed'"""
        mock_manager = AsyncMock()

        mock_db = AsyncMock()
        mock_job = AIGenerationJob(
            id=2,
            document_id=200,
            status="failed",
            progress=50,  # Job already failed
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.background_jobs.database.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock()
            ),
        ):
            with patch("app.services.background_jobs.manager", mock_manager):
                # Run heartbeat
                await send_periodic_heartbeat(
                    user_id=2, job_id=2, document_id=200, interval=0.1
                )

        # Should stop immediately without sending heartbeat (job already failed)
        # It will sleep first, then check status, then stop
        assert mock_manager.send_progress.call_count == 0

    @pytest.mark.asyncio
    async def test_heartbeat_stops_when_job_not_found(self):
        """Test that heartbeat stops gracefully when job not found"""
        mock_manager = AsyncMock()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Job not found
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.background_jobs.database.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock()
            ),
        ):
            with patch("app.services.background_jobs.manager", mock_manager):
                await send_periodic_heartbeat(
                    user_id=3,
                    job_id=999,  # Non-existent job
                    document_id=300,
                    interval=0.1,
                )

        # Should stop without sending heartbeat
        assert mock_manager.send_progress.call_count == 0

    @pytest.mark.asyncio
    async def test_heartbeat_handles_websocket_error_gracefully(self):
        """Test that heartbeat continues even if WebSocket send fails"""
        mock_manager = AsyncMock()

        # First call raises error, second succeeds, third job completes
        call_count = 0

        async def mock_send_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("WebSocket connection lost")
            # Otherwise succeed silently

        mock_manager.send_progress = AsyncMock(side_effect=mock_send_side_effect)

        mock_db = AsyncMock()
        mock_job = AIGenerationJob(id=4, document_id=400, status="running", progress=0)

        db_call_count = 0

        async def mock_execute_side_effect(*args, **kwargs):
            nonlocal db_call_count
            db_call_count += 1

            mock_result = MagicMock()
            if db_call_count <= 2:
                mock_job.status = "running"
            else:
                mock_job.status = "completed"
            mock_result.scalar_one_or_none.return_value = mock_job
            return mock_result

        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)

        with patch(
            "app.services.background_jobs.database.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock()
            ),
        ):
            with patch("app.services.background_jobs.manager", mock_manager):
                # Should not raise exception
                await send_periodic_heartbeat(
                    user_id=4, job_id=4, document_id=400, interval=0.1
                )

        # Should have tried to send heartbeat twice (first failed, second succeeded, then job completed)
        assert mock_manager.send_progress.call_count == 2

    @pytest.mark.asyncio
    async def test_heartbeat_can_be_cancelled(self):
        """Test that heartbeat task can be cancelled gracefully"""
        mock_manager = AsyncMock()

        mock_db = AsyncMock()
        mock_job = AIGenerationJob(id=5, document_id=500, status="running", progress=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.background_jobs.database.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock()
            ),
        ):
            with patch("app.services.background_jobs.manager", mock_manager):
                # Create task
                task = asyncio.create_task(
                    send_periodic_heartbeat(
                        user_id=5,
                        job_id=5,
                        document_id=500,
                        interval=0.5,  # Longer interval
                    )
                )

                # Wait a bit
                await asyncio.sleep(0.2)

                # Cancel task
                task.cancel()

                # Should not raise exception
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected

        # Task was cancelled before first heartbeat could be sent
        # (0.2s wait < 0.5s interval)
        assert mock_manager.send_progress.call_count == 0

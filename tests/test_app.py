"""Test main BardApp creation, bindings, and playback control with YTMusic and AudioPlayer."""

import asyncio
from unittest.mock import MagicMock
from bard.config import BardConfig
from bard.models import Track
from bard.ui.app import BardApp


def test_bard_app_mount_ytmusic(tmp_path):
    config = BardConfig(config_path=tmp_path / "config.json")
    client = MagicMock()
    player = MagicMock()
    app = BardApp(config=config, client=client, player=player)
    assert app.player == player
    assert app.client == client


def test_bard_app_instantiation(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    app = BardApp(cfg, mock_client)

    # Verify binding keys exist
    keys = [b.key for b in app.BINDINGS]
    assert "space" in keys
    assert "tab" in keys
    assert "escape" in keys
    assert "n" in keys
    assert "p" in keys
    assert "+" in keys
    assert "=" in keys
    assert "-" in keys
    assert "q" in keys
    assert app.player is None


def test_handle_drawer_play_resolves_and_plays(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.get_stream_url.return_value = "https://audio.stream/song.mp4"
        mock_player = MagicMock()
        mock_player.play.return_value = True
        mock_player.get_volume.return_value = 70

        app = BardApp(cfg, mock_client, player=mock_player)
        track = Track(
            id="vid123",
            title="Enemy",
            artist="Imagine Dragons",
            album="Arcane",
            duration_seconds=180,
            thumbnail_url="http://art.jpg",
        )

        async with app.run_test():
            app.handle_drawer_play(track)
            await asyncio.sleep(0.1)

            mock_client.get_stream_url.assert_called_with("vid123")
            mock_player.play.assert_called_with("https://audio.stream/song.mp4")
            assert app.current_track == track
            assert app.stage_widget.playback_data is not None
            assert app.stage_widget.playback_data["title"] == "Enemy"
            assert app.stage_widget.playback_data["is_playing"] is True

    asyncio.run(_run())


def test_action_toggle_playback(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()

    app = BardApp(cfg, mock_client, player=mock_player)

    # When actively playing -> pauses
    mock_player.is_playing.return_value = True
    app.action_toggle_playback()
    mock_player.pause.assert_called_once()

    # When paused with loaded track -> resumes
    mock_player.is_playing.return_value = False
    app.current_track = Track("1", "T", "A", "Alb", 100, "")
    app.action_toggle_playback()
    mock_player.resume.assert_called_once()


def test_action_next_and_prev_track(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.get_stream_url.side_effect = lambda tid: f"https://audio/{tid}"
        mock_player = MagicMock()
        mock_player.play.return_value = True

        app = BardApp(cfg, mock_client, player=mock_player)
        t1 = Track("1", "Track 1", "Artist 1", "Album", 120, "")
        t2 = Track("2", "Track 2", "Artist 2", "Album", 150, "")
        t3 = Track("3", "Track 3", "Artist 3", "Album", 200, "")
        app.queue = [t1, t2, t3]
        app.current_index = 0
        app.current_track = t1

        async with app.run_test():
            # Advance to next track
            app.action_next_track()
            await asyncio.sleep(0.1)
            assert app.current_index == 1
            assert app.current_track == t2
            mock_player.play.assert_called_with("https://audio/2")

            # Advance to third track
            app.action_next_track()
            await asyncio.sleep(0.1)
            assert app.current_index == 2
            assert app.current_track == t3
            mock_player.play.assert_called_with("https://audio/3")

            # Return to previous track (position near 0)
            mock_player.get_position.return_value = 1.0
            app.action_prev_track()
            await asyncio.sleep(0.1)
            assert app.current_index == 1
            assert app.current_track == t2
            mock_player.play.assert_called_with("https://audio/2")

    asyncio.run(_run())


def test_action_prev_track_restarts_if_deep_in_track(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()
    mock_player.get_position.return_value = 15.0  # > 3.0 seconds

    app = BardApp(cfg, mock_client, player=mock_player)
    app.queue = [Track("1", "T1", "A1", "Alb", 120, ""), Track("2", "T2", "A2", "Alb", 150, "")]
    app.current_index = 1
    app.stage_widget.playback_data = {"progress_ms": 15000}

    app.action_prev_track()
    mock_player.seek.assert_called_with(-15.0)
    assert app.current_index == 1  # Did not decrement index


def test_action_prev_track_at_index_zero_rewinds_beginning(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()
    mock_player.get_position.return_value = 2.0  # <= 3.0 seconds

    app = BardApp(cfg, mock_client, player=mock_player)
    app.queue = [Track("1", "T1", "A1", "Alb", 120, "")]
    app.current_index = 0
    app.stage_widget.playback_data = {"progress_ms": 2000}

    app.action_prev_track()
    # Should seek -pos (-2.0) to reset to 0:00 rather than seek(0)
    mock_player.seek.assert_called_with(-2.0)
    assert app.stage_widget.playback_data["progress_ms"] == 0


def test_action_volume_up_and_down(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()
    mock_player.get_volume.return_value = 60

    app = BardApp(cfg, mock_client, player=mock_player)
    app.stage_widget.playback_data = {"volume": 60}

    app.action_volume_up()
    mock_player.set_volume.assert_called_with(65)

    mock_player.get_volume.return_value = 65
    app.action_volume_down()
    mock_player.set_volume.assert_called_with(60)


def test_action_quit_pauses_playback(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()

    app = BardApp(cfg, mock_client, player=mock_player)
    app.action_quit()
    mock_player.pause.assert_called_once()


def test_on_progress_tick_syncs_with_player(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_player = MagicMock()
        mock_player.is_playing.return_value = True
        mock_player.get_position.return_value = 42.0
        mock_player.get_duration.return_value = 180.0

        app = BardApp(cfg, mock_client, player=mock_player)
        async with app.run_test():
            app.stage_widget.update_track({"title": "Test Song", "duration_ms": 180000})
            app.on_progress_tick()

            assert app.stage_widget._current_progress_ms == 42000
            assert app.stage_widget.playback_data["progress_ms"] == 42000
            assert app.stage_widget.playback_data["duration_ms"] == 180000

    asyncio.run(_run())


def test_on_progress_tick_auto_advances_on_completion(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.get_stream_url.return_value = "https://audio/track2"
        mock_player = MagicMock()

        app = BardApp(cfg, mock_client, player=mock_player)
        t1 = Track("1", "T1", "A", "Alb", 180, "")
        t2 = Track("2", "T2", "A", "Alb", 200, "")
        app.queue = [t1, t2]
        app.current_index = 0
        app.current_track = t1

        # Simulate track had started and was near the end
        app._had_started = True
        app._last_known_pos = 179.0
        app._last_known_dur = 180.0
        # Now mpv finishes and stops playing
        mock_player.is_playing.return_value = False
        mock_player.get_position.return_value = 0.0
        mock_player.get_duration.return_value = 0.0

        async with app.run_test():
            app.on_progress_tick()
            await asyncio.sleep(0.1)

            # Auto-advanced to next track
            assert app.current_index == 1
            assert app.current_track == t2

    asyncio.run(_run())


def test_on_progress_tick_does_not_advance_when_user_paused(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_player = MagicMock()

        app = BardApp(cfg, mock_client, player=mock_player)
        t1 = Track("1", "T1", "A", "Alb", 180, "")
        t2 = Track("2", "T2", "A", "Alb", 200, "")
        app.queue = [t1, t2]
        app.current_index = 0
        app.current_track = t1

        # Track had started and position is near the end
        app._had_started = True
        app._last_known_pos = 179.0
        app._last_known_dur = 180.0

        # User deliberately paused playback
        mock_player.is_playing.return_value = True
        app.action_toggle_playback()
        assert app._user_paused is True
        mock_player.is_playing.return_value = False

        async with app.run_test():
            app.on_progress_tick()
            await asyncio.sleep(0.1)

            # Must NOT advance to next track because user paused
            assert app.current_index == 0
            assert app.current_track == t1

            # Resume playback
            mock_player.is_playing.return_value = False
            app.action_toggle_playback()
            assert app._user_paused is False

    asyncio.run(_run())

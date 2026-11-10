"""Test main BardApp creation, bindings, and playback control with YTMusic and AudioPlayer."""

import asyncio
from unittest.mock import MagicMock, patch
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


def test_action_quit_pauses_and_closes_player(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()

    app = BardApp(cfg, mock_client, player=mock_player)
    app.action_quit()
    mock_player.pause.assert_called_once()
    mock_player.close.assert_called_once()


def test_on_unmount_closes_player(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    mock_player = MagicMock()

    app = BardApp(cfg, mock_client, player=mock_player)
    app.on_unmount()
    mock_player.close.assert_called_once()


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


def test_bard_app_drawer_callbacks(tmp_path):
    """Verify BardApp passes connect and disconnect callbacks to CurtainDrawer."""
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    app = BardApp(cfg, mock_client)
    assert app.drawer_widget.on_connect_account == app.handle_connect_account
    assert app.drawer_widget.on_disconnect_account == app.handle_disconnect_account


def test_bard_app_handle_connect_account_success(tmp_path):
    """Verify handle_connect_account acquires device code, polls, and updates drawer & client."""
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    app = BardApp(cfg, mock_client)

    mock_oauth = MagicMock()
    mock_oauth.get_device_code.return_value = {
        "device_code": "dev123",
        "user_code": "ABCD-1234",
        "verification_url": "https://www.google.com/device",
        "interval": 1,
    }
    mock_oauth.poll_for_token.return_value = {"access_token": "token123"}
    mock_new_client = MagicMock()

    with patch("bard.ui.app.YTMusicOAuth", return_value=mock_oauth), \
         patch("bard.ui.app.YTMusicClient", return_value=mock_new_client), \
         patch("webbrowser.open") as mock_open, \
         patch.object(app.drawer_widget, "refresh_categories") as mock_refresh, \
         patch.object(app, "notify") as mock_notify:
        app.handle_connect_account()

        mock_oauth.get_device_code.assert_called_once()
        mock_open.assert_called_once_with("https://www.google.com/device")
        mock_oauth.poll_for_token.assert_called_once_with("dev123", interval=1)
        assert app.client == mock_new_client
        assert app.drawer_widget.client == mock_new_client
        mock_refresh.assert_called_once()
        assert mock_notify.call_count >= 2


def test_bard_app_handle_connect_account_failure(tmp_path):
    """Verify handle_connect_account failure paths notify user and do not update client."""
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    app = BardApp(cfg, mock_client)

    # Subcase 1: get_device_code fails
    mock_oauth = MagicMock()
    mock_oauth.get_device_code.return_value = None
    with patch("bard.ui.app.YTMusicOAuth", return_value=mock_oauth), \
         patch.object(app, "notify") as mock_notify:
        app.handle_connect_account()
        assert app.client == mock_client
        mock_notify.assert_called_once()
        assert "Failed" in mock_notify.call_args[0][0]

    # Subcase 2: poll_for_token fails/times out
    mock_oauth2 = MagicMock()
    mock_oauth2.get_device_code.return_value = {
        "device_code": "dev123",
        "user_code": "ABCD-1234",
        "verification_url": "https://www.google.com/device",
        "interval": 1,
    }
    mock_oauth2.poll_for_token.return_value = None
    with patch("bard.ui.app.YTMusicOAuth", return_value=mock_oauth2), \
         patch("webbrowser.open"), \
         patch.object(app, "notify") as mock_notify2:
        app.handle_connect_account()
        assert app.client == mock_client
        assert mock_notify2.call_count >= 2
        assert "timed out or cancelled" in mock_notify2.call_args_list[-1][0][0]


def test_bard_app_handle_connect_account_worker_async(tmp_path):
    """Verify handle_connect_account works inside running Textual event loop via worker."""
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        app = BardApp(cfg, mock_client)

        mock_oauth = MagicMock()
        mock_oauth.get_device_code.return_value = {
            "device_code": "dev123",
            "user_code": "ABCD-1234",
            "verification_url": "https://www.google.com/device",
            "interval": 1,
        }
        mock_oauth.poll_for_token.return_value = {"access_token": "token123"}
        mock_new_client = MagicMock()

        with patch("bard.ui.app.YTMusicOAuth", return_value=mock_oauth), \
             patch("bard.ui.app.YTMusicClient", return_value=mock_new_client), \
             patch("webbrowser.open"):
            async with app.run_test():
                app.handle_connect_account()
                await asyncio.sleep(0.1)
                assert app.client == mock_new_client
                assert app.drawer_widget.client == mock_new_client

    asyncio.run(_run())


def test_bard_app_handle_disconnect_account(tmp_path):
    """Verify handle_disconnect_account clears tokens, creates unauthenticated client, and refreshes drawer."""
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    app = BardApp(cfg, mock_client)

    mock_oauth = MagicMock()
    mock_anon_client = MagicMock()

    with patch("bard.ui.app.YTMusicOAuth", return_value=mock_oauth), \
         patch("bard.ui.app.YTMusicClient", return_value=mock_anon_client), \
         patch.object(app.drawer_widget, "refresh_categories") as mock_refresh, \
         patch.object(app, "notify") as mock_notify:
        app.handle_disconnect_account()

        mock_oauth.clear_tokens.assert_called_once()
        assert app.client == mock_anon_client
        assert app.drawer_widget.client == mock_anon_client
        mock_refresh.assert_called_once()
        mock_notify.assert_called_once_with("Disconnected from YouTube Music.", title="Account")


def test_play_track_worker_notifies_descriptive_stream_error(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.get_stream_url.return_value = None
        mock_client.last_stream_error = "Join this channel to get access to members-only content."
        mock_player = MagicMock()

        app = BardApp(cfg, mock_client, player=mock_player)
        track = Track(
            id="vid_members_only",
            title="Members Only Track",
            artist="Imagine Dragons",
            album="Arcane",
            duration_seconds=180,
            thumbnail_url="http://art.jpg",
        )

        notifications = []

        async with app.run_test():
            app.notify = lambda msg, **kwargs: notifications.append((msg, kwargs))
            app._play_track_worker(track)
            await asyncio.sleep(0.1)

            assert any("Members Only Track" in n[0] and "Join this channel" in n[0] for n in notifications)

    asyncio.run(_run())



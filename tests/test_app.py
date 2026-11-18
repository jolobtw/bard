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


def test_app_handle_shuffle_play(tmp_path):
    """Verify handle_shuffle_play fetches shuffled tracks, updates queue, and begins playback."""
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        shuffled_tracks = [
            Track(id="shuf_1", title="Track 1", artist="Artist", album="Album", duration_seconds=180, thumbnail_url=""),
            Track(id="shuf_2", title="Track 2", artist="Artist", album="Album", duration_seconds=200, thumbnail_url=""),
        ]
        client.get_shuffled_playlist_tracks.return_value = shuffled_tracks
        app = BardApp(cfg, client)
        app.play_track = MagicMock()

        notifications = []
        async with app.run_test():
            app.notify = lambda msg, **kwargs: notifications.append((msg, kwargs))
            app.handle_shuffle_play({"id": "liked", "title": "❤️ Liked Songs", "type": "category"})
            await asyncio.sleep(0.1)

            assert len(app.queue) == 2
            assert app.current_index == 0
            assert app.queue[0].id == "shuf_1"
            app.play_track.assert_called_once_with(shuffled_tracks[0])
            assert app.drawer_widget.tracks == shuffled_tracks
            assert any("Playing" in n[0] and "shuffle" in n[0] for n in notifications)

    asyncio.run(_run())


def test_action_toggle_shuffle_and_restore_order(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    client = MagicMock()
    app = BardApp(cfg, client)

    keys = [b.key for b in app.BINDINGS]
    assert "s" in keys

    tracks = [
        Track(id=f"t{i}", title=f"Song {i}", artist="Artist", album="Album", duration_seconds=120, thumbnail_url="")
        for i in range(6)
    ]
    app.queue = list(tracks)
    app.current_index = 2
    app.current_track = tracks[2]

    app.action_toggle_shuffle()
    assert app.shuffle_enabled is True
    assert app.stage_widget.shuffle_enabled is True
    assert app.current_index == 0
    assert app.queue[0] == tracks[2]
    assert set(t.id for t in app.queue) == set(t.id for t in tracks)

    # Toggling off restores original order and current_index
    app.action_toggle_shuffle()
    assert app.shuffle_enabled is False
    assert app.stage_widget.shuffle_enabled is False
    assert [t.id for t in app.queue] == [t.id for t in tracks]
    assert app.current_index == 2


def test_app_transport_buttons_clickable_in_app(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        client.get_stream_url.side_effect = lambda tid: f"https://audio/{tid}"
        player = MagicMock()
        player.play.return_value = True
        player.is_playing.return_value = True
        player.get_position.return_value = 1.0
        player.get_duration.return_value = 120.0
        player.get_volume.return_value = 70

        app = BardApp(cfg, client, player=player)
        t1 = Track("1", "Track 1", "Artist 1", "Album", 120, "")
        t2 = Track("2", "Track 2", "Artist 2", "Album", 150, "")
        app.queue = [t1, t2]
        app.current_index = 0
        app.current_track = t1

        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.click("#btn-shuffle")
            await pilot.pause()
            assert app.shuffle_enabled is True

            await pilot.click("#btn-repeat")
            await pilot.pause()
            assert app.repeat_mode == "all"

            await pilot.click("#btn-play")
            await pilot.pause()
            player.pause.assert_called_once()

            await pilot.click("#btn-next")
            await pilot.pause()
            await asyncio.sleep(0.1)
            assert app.current_index == 1
            assert app.current_track == t2

            await pilot.click("#btn-prev")
            await pilot.pause()
            await asyncio.sleep(0.1)
            assert app.current_index == 0
            assert app.current_track == t1

    asyncio.run(_run())


def test_action_cycle_repeat_and_playback_modes(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    client = MagicMock()
    player = MagicMock()
    app = BardApp(cfg, client, player=player)

    keys = [b.key for b in app.BINDINGS]
    assert "r" in keys
    assert app.repeat_mode == "off"

    app.action_cycle_repeat()
    assert app.repeat_mode == "all"
    assert app.stage_widget.repeat_mode == "all"

    app.action_cycle_repeat()
    assert app.repeat_mode == "one"
    assert app.stage_widget.repeat_mode == "one"

    app.action_cycle_repeat()
    assert app.repeat_mode == "off"
    assert app.stage_widget.repeat_mode == "off"

    # Repeat all wraps next_track from end of queue to index 0
    t1 = Track("1", "T1", "A", "Alb", 120, "")
    t2 = Track("2", "T2", "A", "Alb", 120, "")
    app.queue = [t1, t2]
    app.current_index = 1
    app.current_track = t2
    app.play_track_at_index = MagicMock()
    app.repeat_mode = "all"
    app.action_next_track()
    app.play_track_at_index.assert_called_once_with(0)

    # Repeat one replays current track on completion
    app.repeat_mode = "one"
    app.play_track = MagicMock()
    app._had_started = True
    app._user_paused = False
    app._last_known_pos = 119.0
    app._last_known_dur = 120.0
    player.is_playing.return_value = False
    app.on_progress_tick()
    app.play_track.assert_called_once_with(t2)


def test_app_shuffle_play_worker_empty_tracks(tmp_path):
    """Verify _shuffle_play_worker gracefully warns when no tracks returned."""
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        client.get_shuffled_playlist_tracks.return_value = []
        app = BardApp(cfg, client)
        app.play_track = MagicMock()

        notifications = []
        async with app.run_test():
            app.notify = lambda msg, **kwargs: notifications.append((msg, kwargs))
            app._shuffle_play_worker("empty_pid", "Empty Playlist")
            await asyncio.sleep(0.1)

            assert len(app.queue) == 0
            app.play_track.assert_not_called()
            assert any("No tracks found to shuffle" in n[0] for n in notifications)

    asyncio.run(_run())


def test_app_shuffle_play_worker_curated_fallback(tmp_path):
    """Verify _shuffle_play_worker falls back to drawer tracks when get_shuffled_playlist_tracks yields empty."""
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        client.get_shuffled_playlist_tracks.return_value = []
        drawer_track = Track(id="t_lofi", title="Lo-Fi Chill", artist="Chill Artist", album="Chill", duration_seconds=150, thumbnail_url="")

        app = BardApp(cfg, client)
        app.drawer_widget.tracks = [drawer_track]
        app.play_track = MagicMock()

        notifications = []
        async with app.run_test():
            app.notify = lambda msg, **kwargs: notifications.append((msg, kwargs))
            app._shuffle_play_worker("lofi", "☕ Lo-Fi Beats")
            await asyncio.sleep(0.1)

            assert len(app.queue) == 1
            assert app.queue[0].id == "t_lofi"
            app.play_track.assert_called_once_with(drawer_track)
            assert any("Playing" in n[0] and "shuffle" in n[0] for n in notifications)

    asyncio.run(_run())


def test_action_toggle_shuffle_and_restore_order(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    client = MagicMock()
    app = BardApp(cfg, client)

    keys = [b.key for b in app.BINDINGS]
    assert "s" in keys

    tracks = [
        Track(id=f"t{i}", title=f"Song {i}", artist="Artist", album="Album", duration_seconds=120, thumbnail_url="")
        for i in range(6)
    ]
    app.queue = list(tracks)
    app.current_index = 2
    app.current_track = tracks[2]

    app.action_toggle_shuffle()
    assert app.shuffle_enabled is True
    assert app.stage_widget.shuffle_enabled is True
    assert app.current_index == 0
    assert app.queue[0] == tracks[2]
    assert set(t.id for t in app.queue) == set(t.id for t in tracks)

    # Toggling off restores original order and current_index
    app.action_toggle_shuffle()
    assert app.shuffle_enabled is False
    assert app.stage_widget.shuffle_enabled is False
    assert [t.id for t in app.queue] == [t.id for t in tracks]
    assert app.current_index == 2


def test_app_transport_buttons_clickable_in_app(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        client.get_stream_url.side_effect = lambda tid: f"https://audio/{tid}"
        player = MagicMock()
        player.play.return_value = True
        player.is_playing.return_value = True
        player.get_position.return_value = 1.0
        player.get_duration.return_value = 120.0
        player.get_volume.return_value = 70

        app = BardApp(cfg, client, player=player)
        t1 = Track("1", "Track 1", "Artist 1", "Album", 120, "")
        t2 = Track("2", "Track 2", "Artist 2", "Album", 150, "")
        app.queue = [t1, t2]
        app.current_index = 0
        app.current_track = t1

        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.click("#btn-shuffle")
            await pilot.pause()
            assert app.shuffle_enabled is True

            await pilot.click("#btn-repeat")
            await pilot.pause()
            assert app.repeat_mode == "all"

            await pilot.click("#btn-play")
            await pilot.pause()
            player.pause.assert_called_once()

            await pilot.click("#btn-next")
            await pilot.pause()
            await asyncio.sleep(0.1)
            assert app.current_index == 1
            assert app.current_track == t2

            await pilot.click("#btn-prev")
            await pilot.pause()
            await asyncio.sleep(0.1)
            assert app.current_index == 0
            assert app.current_track == t1

    asyncio.run(_run())


def test_action_cycle_repeat_and_playback_modes(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    client = MagicMock()
    player = MagicMock()
    app = BardApp(cfg, client, player=player)

    keys = [b.key for b in app.BINDINGS]
    assert "r" in keys
    assert app.repeat_mode == "off"

    app.action_cycle_repeat()
    assert app.repeat_mode == "all"
    assert app.stage_widget.repeat_mode == "all"

    app.action_cycle_repeat()
    assert app.repeat_mode == "one"
    assert app.stage_widget.repeat_mode == "one"

    app.action_cycle_repeat()
    assert app.repeat_mode == "off"
    assert app.stage_widget.repeat_mode == "off"

    # Repeat all wraps next_track from end of queue to index 0
    t1 = Track("1", "T1", "A", "Alb", 120, "")
    t2 = Track("2", "T2", "A", "Alb", 120, "")
    app.queue = [t1, t2]
    app.current_index = 1
    app.current_track = t2
    app.play_track_at_index = MagicMock()
    app.repeat_mode = "all"
    app.action_next_track()
    app.play_track_at_index.assert_called_once_with(0)

    # Repeat one replays current track on completion
    app.repeat_mode = "one"
    app.play_track = MagicMock()
    app._had_started = True
    app._user_paused = False
    app._last_known_pos = 119.0
    app._last_known_dur = 120.0
    player.is_playing.return_value = False
    app.on_progress_tick()
    app.play_track.assert_called_once_with(t2)


def test_app_queue_sync_filter_two_step_esc_and_space_in_input(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        client.get_stream_url.side_effect = lambda tid: f"https://audio/{tid}"
        player = MagicMock()
        player.play.return_value = True
        player.is_playing.return_value = True
        player.get_position.return_value = 0.0
        player.get_duration.return_value = 120.0
        player.get_volume.return_value = 80
        player.get_audio_info.return_value = {"codec": "opus", "samplerate": 48000}
        player.get_audio_devices.return_value = [{"name": "auto", "description": "Default"}]
        player.get_current_audio_device.return_value = "auto"

        app = BardApp(cfg, client, player=player)
        t1 = Track("1", "Track One", "Artist A", "Album", 120, "")
        t2 = Track("2", "Track Two", "Artist B", "Album", 150, "")
        t3 = Track("3", "Night Sky", "Artist C", "Album", 180, "")

        async with app.run_test(size=(110, 40)) as pilot:
            app.drawer_widget.tracks = [t1, t2, t3]
            app.handle_drawer_play(t1)
            await asyncio.sleep(0.1)
            await pilot.pause()

            # Focus queue filter with '/' and type 'track t' (includes space -> must NOT pause)
            await pilot.press("slash")
            await pilot.pause()
            assert app.stage_widget.is_queue_filter_focused() is True
            for ch in ("t", "r", "a", "c", "k", "space", "t"):
                await pilot.press(ch)
            await pilot.pause()
            player.pause.assert_not_called()
            assert app.stage_widget.has_queue_filter_text() is True

            # First Escape blurs filter while keeping query active so Enter selects filtered Track Two
            await pilot.press("escape")
            await pilot.pause()
            assert app.stage_widget.is_queue_filter_focused() is False
            assert app.stage_widget.has_queue_filter_text() is True
            assert app.stage_widget.get_selected_queue_index() == 1

            await pilot.press("enter")
            await asyncio.sleep(0.1)
            await pilot.pause()
            assert app.current_track == t2

            # Second Escape clears filter when drawer is closed and filter is unfocused
            await pilot.press("escape")
            await pilot.pause()
            assert app.stage_widget.has_queue_filter_text() is False

            # J / K navigate queue when drawer closed
            await pilot.press("j")
            await pilot.pause()
            assert app.stage_widget.get_selected_queue_index() >= 1

    asyncio.run(_run())


def test_app_cycle_output_device(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        client = MagicMock()
        player = MagicMock()
        player.is_playing.return_value = False
        player.get_position.return_value = 0.0
        player.get_duration.return_value = 0.0
        player.get_volume.return_value = 75
        player.get_audio_info.return_value = {}
        player.get_audio_devices.return_value = [
            {"name": "auto", "description": "Autoselect device"},
            {"name": "wasapi/{spk}", "description": "Speakers (Realtek)"},
        ]
        player.get_current_audio_device.return_value = "auto"
        player.set_audio_device.return_value = True

        app = BardApp(cfg, client, player=player)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            app.action_cycle_output_device()
            await pilot.pause()
            player.set_audio_device.assert_called_with("wasapi/{spk}")
            assert "Speakers (Realtek)" in str(app.stage_widget.query_one("#output-route").render())

    asyncio.run(_run())






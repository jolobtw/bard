"""End-to-end verification script for YouTube Music playback via AudioPlayer (MPV).

Verifies:
1. YTMusicClient searches and normalizes tracks.
2. Direct audio stream URL resolution via yt-dlp.
3. AudioPlayer spawns headless MPV instance and controls playback over JSON-IPC.
4. Audio plays through local Windows audio hardware for 5 seconds.
5. Track position advances and is_playing() remains True.
6. Volume control can be adjusted and read back accurately.
7. Clean teardown and process exit with code 0.
"""

from __future__ import annotations

import sys
import time

from bard.audio_player import AudioPlayer
from bard.ytmusic_client import YTMusicClient


def main() -> int:
    print("=" * 60)
    print("Bard YouTube Music Playback Verification")
    print("=" * 60)

    # 1. Search YouTube Music
    print("\n[Step 1/6] Searching YouTube Music for 'Daft Punk'...")
    client = YTMusicClient()
    tracks = client.search("Daft Punk", limit=5)
    if not tracks:
        print("ERROR: Search returned no results.")
        return 1

    track = tracks[0]
    print(f"  Found track: {track.artist} - {track.title}")
    print(f"  Track ID: {track.id}")
    print(f"  Duration: {track.duration_seconds}s")

    # 2. Extract stream URL
    print("\n[Step 2/6] Extracting audio stream URL via yt-dlp...")
    stream_url = client.get_stream_url(track.id)
    if not stream_url or not stream_url.startswith("http"):
        print(f"ERROR: Failed to resolve stream URL. Got: {stream_url}")
        return 1
    print(f"  Stream URL resolved: {stream_url[:70]}...")

    # 3. Launch AudioPlayer
    print("\n[Step 3/6] Launching AudioPlayer (MPV IPC engine)...")
    player = AudioPlayer()
    print(f"  Using MPV binary: {player.binary_path}")
    print(f"  IPC pipe/socket: {player.ipc_path}")

    try:
        # 4. Start playback
        print(f"\n[Step 4/6] Starting stream playback...")
        ok = player.play(stream_url)
        if not ok:
            print("ERROR: player.play() returned False")
            return 1

        print("  Waiting for stream to buffer and begin playback...")
        start_wait = time.time()
        playing = False
        while time.time() - start_wait < 15.0:
            if player.is_playing() and player.get_position() > 0:
                playing = True
                break
            time.sleep(0.5)

        if not playing:
            print(f"ERROR: Player did not start playback within 15s (is_playing={player.is_playing()}, pos={player.get_position()})")
            return 1

        initial_pos = player.get_position()
        print(f"  Playback confirmed started at {initial_pos:.2f}s")

        # 5. Play for 5 seconds and monitor position
        print("\n[Step 5/6] Playing audio through local audio hardware for 5 seconds...")
        for second in range(1, 6):
            time.sleep(1.0)
            curr_pos = player.get_position()
            curr_playing = player.is_playing()
            print(f"  [{second}/5s] Position: {curr_pos:.2f}s | Playing: {curr_playing}")

        final_pos = player.get_position()
        if not player.is_playing():
            print("ERROR: Player stopped playing unexpectedly.")
            return 1
        if final_pos <= initial_pos:
            print(f"ERROR: Playback position did not advance (initial={initial_pos:.2f}s, final={final_pos:.2f}s)")
            return 1
        print(f"  Successfully verified {final_pos - initial_pos:.2f}s of active audio progression.")

        # 6. Test volume control
        print("\n[Step 6/6] Testing volume adjustment...")
        original_vol = player.get_volume()
        print(f"  Original volume: {original_vol}%")

        player.set_volume(50)
        time.sleep(0.3)
        vol_50 = player.get_volume()
        print(f"  Set volume to 50% -> Readback: {vol_50}%")
        if abs(vol_50 - 50) > 1:
            print(f"ERROR: Expected volume 50%, got {vol_50}%")
            return 1

        player.set_volume(75)
        time.sleep(0.3)
        vol_75 = player.get_volume()
        print(f"  Set volume to 75% -> Readback: {vol_75}%")
        if abs(vol_75 - 75) > 1:
            print(f"ERROR: Expected volume 75%, got {vol_75}%")
            return 1

        player.set_volume(original_vol)
        time.sleep(0.2)
        print(f"  Restored volume to {original_vol}%")

    finally:
        print("\nCleanly stopping and shutting down MPV player...")
        player.close()
        time.sleep(0.5)

    if player.is_playing():
        print("ERROR: Player reports is_playing() after close()")
        return 1

    print("\n" + "=" * 60)
    print("SUCCESS: Full YouTube Music playback verified end-to-end!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

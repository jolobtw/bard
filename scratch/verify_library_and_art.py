"""Live end-to-end verification script for YouTube Music library access, search, and Hero art.

Verifies:
1. High-resolution album art URL upgrading and 46x20 TrueColor Hero ANSI mosaic rendering.
2. Live Google OAuth 2.0 Device Code flow (RFC 8628).
3. Live multi-type search across songs, albums, and artists.
4. Live album tracklist resolution and thumbnail propagation.
"""

from __future__ import annotations

import sys
import traceback

from bard.art import (
    render_album_art,
    render_placeholder,
    upgrade_thumbnail_url,
)
from bard.oauth import YTMusicOAuth
from bard.ytmusic_client import YTMusicClient


def verify_album_art() -> bool:
    print("\n" + "=" * 60)
    print("[Step 1/4] Verifying High-Resolution Album Art & 46x20 Hero ANSI Rendering")
    print("=" * 60)

    # 1.1 Test URL upgrading regex
    test_w_h_url = "https://lh3.googleusercontent.com/sample=w120-h120"
    upgraded_w_h = upgrade_thumbnail_url(test_w_h_url, target_size=544)
    print(f"  Rewriting: {test_w_h_url} -> {upgraded_w_h}")
    assert "=w544-h544" in upgraded_w_h, f"Expected =w544-h544 in upgraded url, got {upgraded_w_h}"

    test_s_url = "https://yt3.googleusercontent.com/sample=s226"
    upgraded_s = upgrade_thumbnail_url(test_s_url, target_size=544)
    print(f"  Rewriting: {test_s_url} -> {upgraded_s}")
    assert "=s544" in upgraded_s, f"Expected =s544 in upgraded url, got {upgraded_s}"

    # 1.2 Test placeholder dimensions
    placeholder = render_placeholder(width=46, height=20)
    ph_lines = placeholder.splitlines()
    print(f"  Placeholder rendered: {len(ph_lines)} lines (expected 20)")
    assert len(ph_lines) == 20, f"Expected 20 lines, got {len(ph_lines)}"
    assert "\x1b[" in placeholder, "Expected ANSI escape sequences in placeholder"

    # 1.3 Test live image fetch and 46x20 TrueColor ANSI mosaic rendering
    sample_art_url = "https://yt3.googleusercontent.com/N55arCGj69gtw6thXK8JUPisxoVYiwuIEQ7I6SGlkEyNcSJ7xIWPe76Vuu1SiUqRyx5w9qvR_zV8fV3CWQ=w120-h120"
    print(f"  Rendering live album art from: {sample_art_url}")
    ansi_art = render_album_art(sample_art_url, width=46, height=20)
    art_lines = ansi_art.splitlines()
    print(f"  Live art rendered: {len(art_lines)} lines, first line length {len(art_lines[0])} bytes")
    assert len(art_lines) == 20, f"Expected 20 lines, got {len(art_lines)}"
    assert "\u2580" in ansi_art, "Expected half-block characters (\u2580) in rendered art"
    assert "\x1b[38;2;" in ansi_art, "Expected 24-bit TrueColor foreground escape sequences"
    assert "\x1b[48;2;" in ansi_art, "Expected 24-bit TrueColor background escape sequences"

    print("  [SUCCESS] Album art upgrading and Hero mosaic rendering verified.")
    return True


def verify_oauth_device_code() -> bool:
    print("\n" + "=" * 60)
    print("[Step 2/4] Verifying Google OAuth 2.0 Device Code Flow (RFC 8628)")
    print("=" * 60)

    oauth = YTMusicOAuth()
    print(f"  Requesting device code using client ID: {oauth.client_id[:16]}...{oauth.client_id[-20:]}")
    code_data = oauth.get_device_code()

    verification_url = code_data.get("verification_url")
    user_code = code_data.get("user_code")
    device_code = code_data.get("device_code")
    interval = code_data.get("interval")
    expires_in = code_data.get("expires_in")

    print(f"  Verification URL : {verification_url}")
    print(f"  User Code        : {user_code}")
    print(f"  Device Code      : {device_code[:12]}... (hidden)")
    print(f"  Poll Interval    : {interval}s")
    print(f"  Expires In       : {expires_in}s")

    assert verification_url == "https://www.google.com/device", f"Unexpected verification URL: {verification_url}"
    assert user_code and len(user_code) >= 6, f"Invalid user_code: {user_code}"
    assert device_code and len(device_code) > 10, f"Invalid device_code: {device_code}"
    assert isinstance(interval, int) and interval > 0, f"Invalid interval: {interval}"
    assert isinstance(expires_in, int) and expires_in > 0, f"Invalid expires_in: {expires_in}"

    print("  [SUCCESS] Google OAuth device code flow successfully returned valid device authorization.")
    return True


def verify_multi_type_search(client: YTMusicClient) -> dict:
    print("\n" + "=" * 60)
    print("[Step 3/4] Verifying Multi-Type Search (YTMusicClient.search_all)")
    print("=" * 60)

    query = "Daft Punk"
    print(f"  Searching YouTube Music for query: '{query}'...")
    results = client.search_all(query, limit=10)

    songs = results.get("songs", [])
    albums = results.get("albums", [])
    artists = results.get("artists", [])

    print(f"  Results returned: {len(songs)} songs, {len(albums)} albums, {len(artists)} artists")

    assert len(songs) > 0, "Expected at least 1 song result"
    assert len(albums) > 0, "Expected at least 1 album result"
    assert len(artists) > 0, "Expected at least 1 artist result"

    print("\n  Sample Songs:")
    for song in songs[:3]:
        print(f"    - '{song.title}' by {song.artist} ({song.duration_seconds}s) [ID: {song.id}]")

    print("\n  Sample Albums:")
    for alb in albums[:3]:
        print(f"    - '{alb.get('title')}' by {alb.get('artist')} ({alb.get('year')}) [browseId: {alb.get('browse_id')}]")

    print("\n  Sample Artists:")
    for art in artists[:3]:
        print(f"    - '{art.get('name')}' [ID: {art.get('id')}]")

    print("  [SUCCESS] Multi-type search returned categorized results.")
    return results


def verify_album_tracks(client: YTMusicClient, browse_id: str) -> None:
    print("\n" + "=" * 60)
    print(f"[Step 4/4] Verifying Album Track Extraction (browse_id: {browse_id})")
    print("=" * 60)

    tracks = client.get_album_tracks(browse_id)
    print(f"  Retrieved {len(tracks)} tracks for album {browse_id}")
    assert len(tracks) > 0, f"Expected tracks for album {browse_id}, got {len(tracks)}"

    for i, t in enumerate(tracks[:5], start=1):
        print(f"    {i}. {t.artist} - {t.title} ({t.duration_seconds}s)")
        assert t.title, "Track title must not be empty"
        assert t.id, "Track ID must not be empty"

    lead_track = tracks[0]
    if lead_track.thumbnail_url:
        print(f"\n  Rendering 46x20 Hero art for album lead track: {lead_track.title}")
        art = render_album_art(lead_track.thumbnail_url, width=46, height=20)
        lines = art.splitlines()
        assert len(lines) == 20, f"Expected 20 lines, got {len(lines)}"
        # Display the art banner
        print("\n" + art + "\n")
        print(f"  Hero Banner Art: 46 columns x {len(lines)} rows rendered cleanly.")

    print("  [SUCCESS] Album track extraction and art integration verified.")


def main() -> int:
    print("=" * 60)
    print("Bard YouTube Music Library, Search & Hero Art System Verification")
    print("=" * 60)

    try:
        # Step 1: Album art and ANSI rendering
        verify_album_art()

        # Step 2: Google OAuth device code flow
        verify_oauth_device_code()

        # Step 3: Multi-type search
        client = YTMusicClient()
        search_results = verify_multi_type_search(client)

        # Step 4: Album tracks
        album_browse_id = search_results["albums"][0].get("browse_id") or "MPREb_K8qWMWVqXGi"
        verify_album_tracks(client, album_browse_id)

        print("\n" + "=" * 60)
        print("ALL SYSTEM VERIFICATIONS PASSED SUCCESSFULLY!")
        print("=" * 60)
        return 0

    except Exception as exc:
        print(f"\n[VERIFICATION FAILED]: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

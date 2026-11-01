"""Test ZenStage formatting and logic."""

from bard.ui.zen_stage import format_ms, render_flame_progress


def test_format_ms():
    assert format_ms(0) == "00:00"
    assert format_ms(65000) == "01:05"
    assert format_ms(230000) == "03:50"


def test_render_flame_progress():
    output = render_flame_progress(progress_ms=30000, duration_ms=60000, width=30)
    assert "00:30" in output
    assert "01:00" in output
    assert "●" in output


def test_zen_stage_empty_state_rendering():
    from textual.app import App, ComposeResult
    from bard.ui.zen_stage import ZenStage
    from textual.widgets import Static
    import asyncio

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        app = TestApp()
        async with app.run_test():
            stage = app.query_one(ZenStage)
            stage.refresh_stage()
            title = stage.query_one("#track-title", Static)
            assert "STAGE IS SILENT" in str(title.render())
            art = stage.query_one("#art-box", Static)
            assert "ARCANE" in str(art.render()) or "✦" in str(art.render()) or "◈" in str(art.render())

    asyncio.run(_test())


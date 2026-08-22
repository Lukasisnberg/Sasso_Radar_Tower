import pytest

from flugradar.display import fonts, ui_icons


@pytest.fixture(autouse=True)
def _reset_font_cache():
    """Runs for every test in the suite. Many test files each do their
    own pygame.init()/pygame.quit() cycle within the same process; a
    pygame.font.Font cached before one file's pygame.quit() is invalid
    (segfaults, doesn't raise) once the next file's pygame.init() spins
    the font subsystem back up. Clearing fonts.get_font()'s cache after
    every test guarantees no test can inherit a Font handle from a
    subsystem instance that no longer exists."""
    yield
    fonts.reset_cache()


@pytest.fixture(autouse=True)
def _reset_ui_icon_cache():
    """Same reasoning as _reset_font_cache above, for ui_icons.py's cached
    Surfaces (Schritt 1 of the UI overhaul)."""
    yield
    ui_icons.reset_cache()

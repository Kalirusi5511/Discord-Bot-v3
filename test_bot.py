"""Minimale Tests fuer den Discord Sticker Bot."""


def test_imports():
    """Prueft, dass bot.py ohne Fehler importiert werden kann."""
    import bot  # noqa: F401


def test_sanitize_name():
    """Prueft die Namensbereinigung."""
    from bot import sanitize_name

    assert sanitize_name("Hallo Welt") == "hallo_welt"
    assert sanitize_name("  TEST  ") == "test"
    assert sanitize_name("Mein-Sticker") == "mein-sticker"


def test_validate_image_too_large():
    """Prueft, dass zu grosse Dateien abgelehnt werden."""
    from bot import validate_image

    ok, err = validate_image(b"x" * (600 * 1024), ".png")
    assert ok is False
    assert "gross" in err.lower() or "512" in err

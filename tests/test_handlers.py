from bot.keyboards.menus import quality_selection_keyboard, settings_keyboard


def test_quality_selection_keyboard():
    markup = quality_selection_keyboard("job123")
    assert any(button.callback_data == "download:job123:best" for row in markup.inline_keyboard for button in row)
    assert any(button.callback_data == "download:job123:mp3" for row in markup.inline_keyboard for button in row)


def test_settings_keyboard_contains_buttons():
    markup = settings_keyboard()
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "settings:workers:+1" in callbacks
    assert "settings:rate_limit:-1" in callbacks

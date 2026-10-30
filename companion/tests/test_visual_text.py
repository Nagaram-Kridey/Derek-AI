from desktop.visual_text import TextBox, exact_region_match


def test_recipient_must_be_exact_and_inside_dedicated_region():
    region = (0, 0, 200, 50)
    assert exact_region_match([TextBox('MSV Krishna', 5, 5, 100, 20)], 'MSV Krishna', region)
    for text in ('MSV Krishna Junior', 'MSV', 'MSV Krіshna'):
        assert not exact_region_match([TextBox(text, 5, 5, 100, 20)], 'MSV Krishna', region)
    assert not exact_region_match([TextBox('MSV Krishna', 5, 80, 100, 20)], 'MSV Krishna', region)
    assert not exact_region_match([TextBox('MSV Krishna', 150, 5, 100, 20)], 'MSV Krishna', region)


def test_duplicate_matches_and_empty_recipient_fail_closed():
    box = TextBox('Draft', 5, 5, 50, 20)
    assert not exact_region_match([box, box], 'Draft', (0, 0, 200, 50))
    assert not exact_region_match([], '', (0, 0, 200, 50))

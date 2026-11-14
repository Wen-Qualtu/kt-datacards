import fitz
import pytest

from pipeline.steps import generate_card_images
from pipeline.steps.generate_card_images import (
    _can_reuse_card,
    _card_text_signature,
    _prune_stale_card_images,
    _stale_card_images,
)
from pipeline.steps.tts_impl import _prune_stale_individual_card_jsons
from pipeline.utils.card_naming import detect_type, extract_name


def _pdf_with_text(text: str, title: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    metadata = doc.metadata
    metadata["title"] = title
    doc.set_metadata(metadata)
    return doc.tobytes()


def test_stonesinger_upgrade_is_classified_as_faction_rule() -> None:
    lines = ["EXODITE DRAGON MASTER", "STONESINGER UPGRADE", "EARTHEN WRATH"]

    assert detect_type(lines) == "faction-rules"
    assert extract_name(lines) == "earthen-wrath"


def test_card_text_signature_ignores_metadata_and_whitespace() -> None:
    first = _pdf_with_text("Vox   Operator", "first export")
    second = _pdf_with_text("Vox Operator", "second export")

    assert _card_text_signature(first, "cache-test-team", False) == _card_text_signature(
        second, "cache-test-team", False
    )


def test_card_text_signature_changes_when_card_text_changes() -> None:
    first = _pdf_with_text("Vox Operator", "same export")
    changed = _pdf_with_text("Vox Operator revised", "same export")

    assert _card_text_signature(first, "cache-test-team", False) != _card_text_signature(
        changed, "cache-test-team", False
    )


def test_reuse_requires_matching_text_existing_images_and_no_force(tmp_path) -> None:
    front = tmp_path / "front.jpg"
    back = tmp_path / "back.jpg"
    front.write_bytes(b"front")
    back.write_bytes(b"back")

    assert _can_reuse_card("same", "same", [front, back], False)
    assert not _can_reuse_card("old", "new", [front, back], False)
    assert not _can_reuse_card("same", "same", [front, tmp_path / "missing.jpg"], False)
    assert not _can_reuse_card("same", "same", [front, back], True)


def test_process_team_reuses_unchanged_card_images(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "card.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    output_root = tmp_path / "output"
    front = output_root / "cards" / "datacards" / "operative-front.jpg"
    back = output_root / "cards" / "datacards" / "operative-back.jpg"
    front.parent.mkdir(parents=True)
    front.write_bytes(b"existing front")
    back.write_bytes(b"existing back")

    entries = [("datacards", "operative", pdf_path, False)]
    monkeypatch.setattr(generate_card_images, "_team_card_entries", lambda team: entries)
    monkeypatch.setattr(generate_card_images, "_card_text_signature", lambda *args: "same")
    monkeypatch.setattr(generate_card_images, "_head_card_text_signature", lambda *args: "same")
    monkeypatch.setattr(generate_card_images.paths, "team_output", lambda team: output_root)
    monkeypatch.setattr(
        generate_card_images,
        "_render_page",
        lambda *args: pytest.fail("unchanged card should not be rendered"),
    )

    result = generate_card_images._process_team("test-team", {}, False)

    assert result == (0, 2, {"datacards/operative": "same"}, 1)
    assert front.read_bytes() == b"existing front"
    assert back.read_bytes() == b"existing back"


def test_process_team_renders_changed_card(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "card.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    entries = [("datacards", "operative", pdf_path, False)]
    rendered_pages = []
    monkeypatch.setattr(generate_card_images, "_team_card_entries", lambda team: entries)
    monkeypatch.setattr(generate_card_images, "_card_text_signature", lambda *args: "new")
    monkeypatch.setattr(generate_card_images, "_head_card_text_signature", lambda *args: "old")
    monkeypatch.setattr(
        generate_card_images,
        "_render_page",
        lambda doc, page, output: rendered_pages.append(page) or True,
    )

    result = generate_card_images._process_team("test-team", {}, False)

    assert rendered_pages == [0, 1]
    assert result == (2, 0, {"datacards/operative": "new"}, 1)


def test_prune_stale_card_images_preserves_manifest_outputs(tmp_path) -> None:
    cards_root = tmp_path / "cards"
    current = cards_root / "faction_rules" / "new-rule-front.jpg"
    stale = cards_root / "faction_rules" / "old-rule-front.jpg"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"current")
    stale.write_bytes(b"stale")

    removed = _prune_stale_card_images(cards_root, {current})

    assert removed == [stale]
    assert current.exists()
    assert not stale.exists()


def test_stale_card_images_prevent_cache_skip(tmp_path) -> None:
    cards_root = tmp_path / "cards"
    stale = cards_root / "faction_rules" / "removed-rule-front.jpg"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")

    assert _stale_card_images(cards_root, set()) == [stale]


def test_prune_stale_individual_card_jsons_preserves_current_cards(tmp_path) -> None:
    cards_root = tmp_path / "tts_objects" / "cards"
    current = cards_root / "faction-rules" / "new-rule.json"
    stale = cards_root / "faction-rules" / "old-rule.json"
    current.parent.mkdir(parents=True)
    current.write_text("{}", encoding="utf-8")
    stale.write_text("{}", encoding="utf-8")

    removed = _prune_stale_individual_card_jsons(cards_root, {current})

    assert removed == [stale]
    assert current.exists()
    assert not stale.exists()

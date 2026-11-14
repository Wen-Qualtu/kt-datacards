from pathlib import Path

import pytest

from pipeline.steps import track_warcom


@pytest.mark.parametrize("force", [False, True])
def test_scrape_filters_by_team_identity_including_aliases(tmp_path, monkeypatch, force):
    urls = [
        "https://example.test/eng_murderwing_online_rules-current.pdf",
        "https://example.test/eng_murderwings_online_rules-previous.pdf",
        "https://example.test/eng_blooded_online_rules.pdf",
        "https://example.test/eng_unknown_online_rules.pdf",
    ]
    team_config = {
        "murderwings": {"canonical_name": "Murderwings", "aliases": ["murderwing"]},
        "blooded": {"canonical_name": "Blooded"},
    }
    staging = tmp_path / "staging"
    archive = tmp_path / "archive"
    downloads = []

    async def extract_urls(url, section):
        return urls

    def download(url, output):
        downloads.append(url)
        output.write_bytes(b"pdf")
        return True

    monkeypatch.setattr(track_warcom.scraper, "extract_pdf_urls_from_page", extract_urls)
    monkeypatch.setattr(track_warcom.scraper, "download_pdf", download)
    monkeypatch.setattr(track_warcom.card_extractor, "load_team_config", lambda path: team_config)
    monkeypatch.setattr(track_warcom.paths, "staging_dir", lambda track: staging)
    monkeypatch.setattr(track_warcom.paths, "staging_archive_dir", lambda track: archive)

    result = track_warcom._scrape(["murderwings"], force)

    assert downloads == urls[:2]
    assert result == [staging / Path(url).name for url in urls[:2]]


def test_scrape_uses_longest_matching_team_identity(tmp_path, monkeypatch):
    urls = [
        "https://example.test/eng_chaos_cult_online_rules.pdf",
        "https://example.test/eng_chaos_cult_elite_online_rules.pdf",
    ]
    team_config = {"chaos-cult": {}, "chaos-cult-elite": {}}
    staging = tmp_path / "staging"
    downloads = []

    async def extract_urls(url, section):
        return urls

    def download(url, output):
        downloads.append(url)
        output.write_bytes(b"pdf")
        return True

    monkeypatch.setattr(track_warcom.scraper, "extract_pdf_urls_from_page", extract_urls)
    monkeypatch.setattr(track_warcom.scraper, "download_pdf", download)
    monkeypatch.setattr(track_warcom.card_extractor, "load_team_config", lambda path: team_config)
    monkeypatch.setattr(track_warcom.paths, "staging_dir", lambda track: staging)
    monkeypatch.setattr(track_warcom.paths, "staging_archive_dir", lambda track: tmp_path / "archive")

    assert track_warcom._scrape(["chaos-cult"], False) == [staging / Path(urls[0]).name]
    assert downloads == urls[:1]

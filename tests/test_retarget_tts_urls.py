import json

from tools.retarget_tts_urls import normalize_references, retarget_bytes


def test_retargets_only_own_repository_urls_and_preserves_every_other_byte():
    before = b'{\r\n  "GUID": "abc123", "Name": "main", "hash": "unchanged",\r\n' \
        b'  "url": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/a.json?v=123",\r\n' \
        b'  "external": "https://example.test/main/output/a.json"\r\n}\r\n'
    after, count = retarget_bytes(before)
    assert count == 1
    assert after == before.replace(b"kt-datacards/main/", b"kt-datacards/acc/")
    assert normalize_references(before) == normalize_references(after)
    assert json.loads(after)["hash"] == "unchanged"
    assert retarget_bytes(after) == (after, 0)


def test_retargets_embedded_lua_urls_and_bare_repository_bases_without_reformatting():
    before = json.dumps({
        "LuaScript": 'local base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"\n'
            'local loader = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refs/heads/feature/command-node/output/loader.lua?v=9"',
        "GMNotes": '{"name":"Operative","stats":{"Wounds":8}}',
        "Transform": {"rotY": 90, "posX": 1.25},
    }, indent=2).encode("utf-8")
    after, count = retarget_bytes(before)
    assert count == 2
    assert b"refs/heads/acc/output/loader.lua?v=9" in after
    assert json.loads(after)["GMNotes"] == json.loads(before)["GMNotes"]
    assert json.loads(after)["Transform"] == json.loads(before)["Transform"]
    assert normalize_references(before) == normalize_references(after)


def test_does_not_change_other_branches_or_template_variables():
    before = b'https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main-other/output/a.json\n' \
        b'https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/output/a.json'
    assert retarget_bytes(before) == (before, 0)
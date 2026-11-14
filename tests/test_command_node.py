import json
import os
import shutil
import subprocess
import sys

import pytest

from pipeline.steps import extract_stats, generate_tts, tts_impl
from pipeline.utils.ktui_model_script import compose_command_node_loader
from tools.build_command_node import ROOT, SCRIPT, build_save

CONFIG = ROOT / "config"


def embedded_card_data(box):
    return {
        data["name"]: data
        for card in tts_impl._find_datacards(box)
        if card.get("GMNotes") and "function diffAndApply" in card.get("LuaScript", "")
        for data in [json.loads(card["GMNotes"])]
        if data.get("name") and data.get("stats")
    }


def lua_literal(value):
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"' + "".join(f"\\{byte:03d}" for byte in value.encode("utf-8")) + '"'
    if isinstance(value, list):
        return "{" + ",".join(lua_literal(item) for item in value) + "}"
    return "{" + ",".join(f"[{lua_literal(key)}]={lua_literal(item)}" for key, item in value.items()) + "}"


@pytest.mark.skipif(not os.environ.get("COMMAND_NODE_LUA_PARITY"), reason="optional Lua parity check")
def test_real_team_data_converts_to_existing_card_fields():
    npx = shutil.which("npx")
    assert npx, "npx is required for the optional Lua parity check"
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    cases = []
    for slug, title in [
        ("blades-of-khaine", "Blades Of Khaine"),
        ("warpcoven", "Warpcoven"),
        ("exodite-dragon-masters", "Exodite Dragon Masters"),
    ]:
        team_path = ROOT / "output" / slug / "data" / f"{slug}-team-data.json"
        box_path = ROOT / "output" / slug / "tts_objects" / f"{title}.json"
        team = extract_stats.add_node_fields(json.loads(team_path.read_text(encoding="utf-8")), rules)
        cards = embedded_card_data(json.loads(box_path.read_text(encoding="utf-8")))
        for operative in team["datacards"]:
            if operative["name"] not in cards:
                continue
            expected = dict(cards[operative["name"]])
            expected.pop("description", None)
            expected.pop("upgrades", None)
            cases.append({"operative": operative, "rules": team["node_weapon_rules"], "expected": expected})

    lua = """
dofile("config/defaults/tts-script/command-node.lua")
local cases = CASES
local function equal(left, right)
    if type(left) ~= type(right) then return false end
    if type(left) ~= "table" then return left == right end
    for key, value in pairs(left) do if not equal(value, right[key]) then return false end end
    for key in pairs(right) do if left[key] == nil then return false end end
    return true
end
for _, case in ipairs(cases) do
    local actual, reason = commandNodeModelData(case.operative, case.rules)
    assert(actual and equal(actual, case.expected), case.operative.name .. ": " .. tostring(reason))
end
print("parity " .. #cases)
""".replace("CASES", lua_literal(cases))
    result = subprocess.run(
        [npx, "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=lua, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == f"parity {len(cases)}", result.stderr


def test_node_fields_reuse_card_loadout_indexes_without_changing_existing_data():
    team_path = ROOT / "output" / "blades-of-khaine" / "data" / "blades-of-khaine-team-data.json"
    box_path = ROOT / "output" / "blades-of-khaine" / "tts_objects" / "Blades Of Khaine.json"
    team = json.loads(team_path.read_text(encoding="utf-8"))
    box = json.loads(box_path.read_text(encoding="utf-8"))
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    enriched = extract_stats.add_node_fields(team, rules)
    expected = embedded_card_data(box)

    for original, operative in zip(team["datacards"], enriched["datacards"]):
        node = operative.pop("node")
        original_fields = dict(original)
        original_fields.pop("node", None)
        assert operative == original_fields
        model = expected[original["name"]]
        assert node.get("selection") == model.get("selection")
        assert {name: enriched["node_weapon_rules"][name] for name in node["weapon_rule_names"]} == model["weapon_rules"]
        assert len(node["weapon_types"]) == len(original.get("weapons", []))
        assert node["weapon_types"] == [
            "melee" if weapon["name"].startswith("[F4641D]M[-]") else "ranged"
            for weapon in model["weapons"]
        ]


def test_canoptek_warrior_and_crawler_loadout_options_are_precomputed():
    team = json.loads((ROOT / "output/canoptek-circle/data/canoptek-circle-team-data.json").read_text(encoding="utf-8"))
    nodes = {
        operative["name"]: operative["node"]["selection"]
        for operative in team["datacards"]
        if operative["name"] in {"CANOPTEK MACROCYTE WARRIOR", "CANOPTEK TOMB CRAWLER"}
    }

    assert [option["label"] for option in nodes["CANOPTEK MACROCYTE WARRIOR"]["groups"][0]] == [
        "Gauss scalpel; claws and tail", "Tesla caster; claws and tail"
    ]
    assert [option["label"] for option in nodes["CANOPTEK TOMB CRAWLER"]["groups"][0]] == [
        "Twin gauss reapers; claws", "Transdimensional isolator; claws"
    ]


def test_all_team_node_fields_match_existing_card_loadouts():
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    for path in sorted((ROOT / "output").glob("*/data/*-team-data.json")):
        team = json.loads(path.read_text(encoding="utf-8"))
        slug = team["team"]
        box_path = ROOT / "output" / slug / "tts_objects" / f"{slug.replace('-', ' ').title()}.json"
        assert box_path.exists(), slug
        cards = embedded_card_data(json.loads(box_path.read_text(encoding="utf-8")))
        enriched = extract_stats.add_node_fields(team, rules)
        selections = team.get("operatives_selection") or []
        groups_by_name = selections[0].get("selection", {}) if selections else {}
        for original, operative in zip(team["datacards"], enriched["datacards"]):
            name = operative["name"]
            assert name in cards, f"{slug}: {name} has no card data"
            node = operative["node"]
            model = cards[name]
            assert node.get("selection") == model.get("selection"), f"{slug}: {name} loadout"
            assert {rule: enriched["node_weapon_rules"][rule] for rule in node["weapon_rule_names"]} == model["weapon_rules"], f"{slug}: {name} rules"
            assert node["weapon_types"] == [
                "melee" if weapon["name"].startswith("[F4641D]M[-]") else "ranged"
                for weapon in model["weapons"]
            ], f"{slug}: {name} weapon classification"
            groups = groups_by_name.get(name.upper()) or []
            before = tts_impl._build_gm_notes(original, team, rules, selection_groups=groups)
            after = tts_impl._build_gm_notes(operative, enriched, rules, selection_groups=groups)
            assert before == after, f"{slug}: {name} card-box data changed"


def test_saved_object_embeds_current_node_script():
    script = SCRIPT.read_text(encoding="utf-8")
    save = json.loads(json.dumps(build_save(script)))

    assert save["SaveName"] == "Kill Team Command Node"
    assert len(save["ObjectStates"]) == 1
    node = save["ObjectStates"][0]
    assert node["Name"] == "Custom_Tile"
    assert node["CustomImage"]["CustomTile"] == {
        "Type": 1, "Thickness": 0.2, "Stackable": False, "Stretch": True,
    }
    assert node["CustomImage"]["ImageURL"].endswith("C19BB145DB4C70E131F1184AC1C81EC5EC446D31/")
    assert node["ColorDiffuse"] == {"r": 0.2, "g": 0.2, "b": 0.2}
    assert node["Transform"]["scaleX"] == node["Transform"]["scaleZ"] == 1
    assert save["ObjectStates"][0]["LuaScript"] == script
    assert "function commandNodeConfirm" in script
    assert "NODE_TEAM_DATA" not in script
    assert "NODE_APPLY_SCRIPT" not in script


def test_existing_card_loadouts_are_preserved():
    path = ROOT / "output" / "angels-of-death" / "tts_objects" / "Angels Of Death.json"
    box = json.loads(path.read_text(encoding="utf-8"))
    cards = embedded_card_data(box)
    sergeant = cards["ASSAULT INTERCESSOR SERGEANT"]

    assert len(cards) == 9
    assert sergeant["selection"]["exclusive_sets"] == [[0, 1], [2]]
    assert "script" not in sergeant
    assert len(json.dumps(cards, ensure_ascii=False)) < path.stat().st_size / 10


def test_embedded_card_data_matches_warpcoven_datacards():
    path = ROOT / "output" / "warpcoven" / "tts_objects" / "Warpcoven.json"
    box = json.loads(path.read_text(encoding="utf-8"))

    cards = embedded_card_data(box)
    deck = next(item for item in box["ContainedObjects"] if item["Nickname"] == "Datacards")
    expected = sorted(
        (json.loads(card["GMNotes"]) for card in deck["ContainedObjects"]),
        key=lambda card: card["name"].lower(),
    )
    assert sorted(cards.values(), key=lambda card: card["name"].lower()) == expected


def test_pipeline_writes_combined_stable_team_data(tmp_path):
    path = ROOT / "output" / "warpcoven" / "data" / "warpcoven-team-data.json"
    team = json.loads(path.read_text(encoding="utf-8"))
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    enriched = extract_stats.add_node_fields(team, rules)
    target = tmp_path / "warpcoven-team-data.json"
    assert extract_stats._save_stable(enriched, target)
    timestamp = target.stat().st_mtime_ns
    original_bytes = target.read_bytes()
    result = json.loads(target.read_text(encoding="utf-8"))

    assert result["team"] == "warpcoven"
    assert all("node" in card for card in result["datacards"])
    assert extract_stats._save_stable(enriched, target)
    assert target.read_bytes() == original_bytes
    assert abs(target.stat().st_mtime_ns - timestamp) < 1_000


def test_legacy_node_cleanup_preserves_other_files_and_state(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    legacy = data / "test-team-node-data.json"
    legacy.write_text("old", encoding="utf-8")
    team_data = data / "test-team-team-data.json"
    team_data.write_text("current", encoding="utf-8")

    class FakeState:
        state = {"steps": {"generate_tts": {"outputs": {
            "data/test-team-node-data.json": {"path": "old"},
            "tts_objects/Test Team.json": {"path": "box"},
        }}}}

    state = FakeState()
    extract_stats.remove_legacy_node_data("test-team", tmp_path, state)
    assert not legacy.exists()
    assert team_data.read_text(encoding="utf-8") == "current"
    assert state.state["steps"]["generate_tts"]["outputs"] == {
        "tts_objects/Test Team.json": {"path": "box"}
    }
    extract_stats.remove_legacy_node_data("test-team", tmp_path, state)


def test_stats_keeps_legacy_data_if_combined_save_fails(tmp_path, monkeypatch):
    team_dir = tmp_path / "test-team"
    data = team_dir / "data"
    data.mkdir(parents=True)
    legacy = data / "test-team-node-data.json"
    legacy.write_text("old", encoding="utf-8")
    content = tmp_path / "content.json"
    content.write_text('{"team":"test-team","datacards":[]}', encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    (config / "weapon_rules.json").write_text("{}", encoding="utf-8")

    class FakeState:
        def __init__(self, team):
            self.state = {"steps": {"generate_tts": {"outputs": {}}}}

        def can_skip(self, step, inputs, force):
            return True

    class FakeIndex:
        def rebuild_and_save(self):
            pass

    monkeypatch.setattr(extract_stats.paths, "team_output", lambda team: team_dir)
    monkeypatch.setattr(extract_stats.paths, "content_file", lambda team: content)
    monkeypatch.setattr(extract_stats.paths, "CONFIG", config)
    monkeypatch.setattr(extract_stats, "StateManager", FakeState)
    monkeypatch.setattr(extract_stats, "StateIndex", FakeIndex)
    monkeypatch.setattr(extract_stats, "_save_stable", lambda data, path: False)

    assert extract_stats.run(teams=["test-team"])["failed"] == 1
    assert legacy.read_text(encoding="utf-8") == "old"


def test_team_data_is_published_and_existing_box_input_is_preserved(tmp_path, monkeypatch):
    team_dir = tmp_path / "output" / "test-team"
    (team_dir / "data").mkdir(parents=True)
    (team_dir / "tts_objects").mkdir()
    team_data = team_dir / "data" / "test-team-team-data.json"
    team_data.write_text('{"team":"test-team","datacards":[]}', encoding="utf-8")
    node_data = team_dir / "data" / "test-team-node-data.json"
    node_data.write_text('{"team":"test-team","operatives":[]}', encoding="utf-8")
    (team_dir / "tts_objects" / "Test Team.json").write_text("{}", encoding="utf-8")
    scripts = tmp_path / "config" / "defaults" / "tts-script"
    scripts.mkdir(parents=True)
    node_script = scripts / "command-node.lua"
    node_script.write_text("node", encoding="utf-8")
    card_script = scripts / "datacard-load-stats.lua"
    card_script.write_text("card", encoding="utf-8")
    monkeypatch.setattr(tts_impl, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generate_tts.paths, "team_output", lambda team: team_dir)
    monkeypatch.setattr(generate_tts.paths, "CONFIG", tmp_path / "config")
    monkeypatch.setattr(generate_tts.paths, "DEFAULTS", tmp_path / "config" / "defaults")
    monkeypatch.setattr(generate_tts.paths, "TEAM_CONFIG", tmp_path / "config" / "team-config.yaml")

    metadata = tts_impl.generate_object_urls_json("feature/command-node")
    summary = tts_impl.generate_object_urls_summary(metadata, "feature/command-node")

    assert "/data/test-team-team-data.json?v=" in metadata["test-team"]["team_data"]["url"]
    assert "feature/command-node" in summary["test-team"]["team_url"]
    assert metadata["test-team"]["team_data"]["hash"][:12] in summary["test-team"]["team_url"]
    assert node_data not in generate_tts._inputs_for("test-team")
    assert team_data in generate_tts._inputs_for("test-team")
    assert node_script not in generate_tts._inputs_for("test-team")
    assert card_script in generate_tts._inputs_for("test-team")

    (team_dir / "test-team-object-urls.json").write_text(
        json.dumps(metadata["test-team"]), encoding="utf-8"
    )
    monkeypatch.setattr(tts_impl, "_git_unchanged_from_head", lambda path: True)
    team_data.write_text('{"team":"test-team","datacards":[{"name":"new"}]}', encoding="utf-8")
    updated = tts_impl.generate_object_urls_json("feature/command-node")
    updated_summary = tts_impl.generate_object_urls_summary(updated, "feature/command-node")
    assert updated["test-team"]["team_data"]["url"] != metadata["test-team"]["team_data"]["url"]
    assert updated_summary["test-team"]["team_url"] != summary["test-team"]["team_url"]
    assert updated_summary["test-team"]["modified"] == summary["test-team"]["modified"]


def test_missing_legacy_node_data_does_not_trigger_tts_generation(tmp_path, monkeypatch):
    team_dir = tmp_path / "test-team"
    tts_dir = team_dir / "tts_objects"
    tts_dir.mkdir(parents=True)
    (tts_dir / "Test Team.json").write_text("{}", encoding="utf-8")
    runs = []

    class FakeState:
        def __init__(self, team):
            self.team = team
            self.state = {"steps": {}}

        def can_skip(self, step, inputs, force):
            return True

        def record_output(self, step, key, path):
            pass

        def record_inputs(self, step, inputs):
            pass

        def mark_complete(self, step):
            pass

        def save(self):
            pass

    class FakeIndex:
        def rebuild_and_save(self):
            pass

    def generate(urls, config_dir, output_dir, team_filter, repo_branch):
        runs.append(team_filter)
        node_data = team_dir / "data" / "test-team-node-data.json"
        node_data.parent.mkdir(exist_ok=True)
        node_data.write_text("{}", encoding="utf-8")
        return 1

    monkeypatch.setattr(generate_tts, "StateManager", FakeState)
    monkeypatch.setattr(generate_tts, "StateIndex", FakeIndex)
    monkeypatch.setattr(generate_tts.paths, "team_output", lambda team: team_dir)
    monkeypatch.setattr(generate_tts.paths, "OUTPUT", tmp_path)
    monkeypatch.setattr(generate_tts, "_inputs_for", lambda team: [])
    monkeypatch.setattr(generate_tts, "_write_object_urls", lambda branch: None)
    monkeypatch.setattr(tts_impl, "generate_urls_json_v3", lambda branch: [])
    monkeypatch.setattr(tts_impl, "generate_all_tts_objects", generate)
    monkeypatch.setattr(tts_impl, "write_command_node_loader", lambda config_dir, output_dir: None)
    monkeypatch.setattr(tts_impl, "rebuild_kill_team_card_boxes_example", lambda output_dir: (0, None))

    assert generate_tts.run(teams=["test-team"])["skipped"] == 1
    assert generate_tts.run(teams=["test-team"])["skipped"] == 1
    assert runs == []


def test_missing_legacy_box_state_is_pruned_without_removing_current_outputs(tmp_path, monkeypatch):
    team_dir = tmp_path / "output" / "test-team"
    tts_dir = team_dir / "tts_objects"
    tts_dir.mkdir(parents=True)
    current = tts_dir / "Test Team.json"
    current.write_text("{}", encoding="utf-8")
    legacy = tts_dir / "Test Team Box.json"

    class FakeState:
        state = {"steps": {"generate_tts": {"outputs": {
            "tts_objects/Test Team Box.json": {"path": "output/test-team/tts_objects/Test Team Box.json"},
            "tts_objects/Test Team.json": {"path": "output/test-team/tts_objects/Test Team.json"},
        }}}}

    monkeypatch.setattr(generate_tts.paths, "ROOT", tmp_path)
    monkeypatch.setattr(generate_tts.paths, "team_output", lambda team: team_dir)
    state = FakeState()
    assert generate_tts._prune_missing_legacy_box(state, "test-team")
    assert "tts_objects/Test Team.json" in state.state["steps"]["generate_tts"]["outputs"]
    assert current.exists()
    assert not generate_tts._prune_missing_legacy_box(state, "test-team")
    state.state["steps"]["generate_tts"]["outputs"]["tts_objects/Test Team Box.json"] = {
        "path": "output/test-team/tts_objects/Test Team Box.json"
    }
    legacy.write_text("{}", encoding="utf-8")
    assert not generate_tts._prune_missing_legacy_box(state, "test-team")
    assert legacy.exists()


def test_tts_saves_repaired_state_even_when_team_is_skipped(tmp_path, monkeypatch):
    saved = []

    class FakeState:
        def __init__(self, team):
            self.team = team

        def can_skip(self, step, inputs, force):
            return True

        def save(self):
            saved.append(self.team)

    class FakeIndex:
        def rebuild_and_save(self):
            pass

    monkeypatch.setattr(generate_tts, "StateManager", FakeState)
    monkeypatch.setattr(generate_tts, "StateIndex", FakeIndex)
    monkeypatch.setattr(generate_tts, "_inputs_for", lambda team: [])
    monkeypatch.setattr(generate_tts, "_prune_missing_legacy_box", lambda state, team: True)
    monkeypatch.setattr(generate_tts, "_write_object_urls", lambda branch: None)
    monkeypatch.setattr(tts_impl, "write_command_node_loader", lambda config_dir, output_dir: None)
    monkeypatch.setattr(tts_impl, "rebuild_kill_team_card_boxes_example", lambda output_dir: (0, None))

    assert generate_tts.run(teams=["test-team"])["skipped"] == 1
    assert saved == ["test-team"]


def test_builder_can_target_a_feature_branch_without_embedded_data(tmp_path):
    output = tmp_path / "node.json"
    subprocess.run(
        [sys.executable, "-m", "tools.build_command_node", "--output", str(output),
         "--branch", "feature/command-node"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    node = json.loads(output.read_text(encoding="utf-8"))["ObjectStates"][0]["LuaScript"]

    assert "refs/heads/feature/command-node" in node
    assert "NODE_TEAM_DATA" not in node
    assert "NODE_APPLY_SCRIPT" not in node
    assert "NODE_LOADER_FALLBACK" not in node
    assert "KTUI_MODELSCRIPT =" not in node
    assert "MOVE_TOOL_CODE =" not in node
    assert "SPRINT_TOOL_CODE =" not in node
    assert len(node.encode("utf-8")) < 45_000


def test_shared_helper_includes_composed_model_and_card_loader():
    helper = compose_command_node_loader(CONFIG)

    assert "KTUI_MODELSCRIPT_VERSION" in helper
    assert "function diffAndApply" in helper
    assert "function rebuildDescription" in helper
    assert "function onLoad" in helper
    scripts = CONFIG / "defaults" / "tts-script"
    assert (scripts / "move-tool.lua").read_text(encoding="utf-8") in helper
    assert (scripts / "sprint-movement-tool.lua").read_text(encoding="utf-8") in helper


def test_pipeline_shared_loader_matches_existing_composition(tmp_path):
    target = tts_impl.write_command_node_loader(CONFIG, tmp_path)
    assert target.read_text(encoding="utf-8") == compose_command_node_loader(CONFIG)
    timestamp = target.stat().st_mtime_ns
    assert tts_impl.write_command_node_loader(CONFIG, tmp_path).stat().st_mtime_ns == timestamp


def test_standalone_token_bag_preserves_contents_and_script(tmp_path):
    bag = {
        "Name": "Custom_Model_Bag", "LuaScript": "bag script", "LuaScriptState": "saved layout",
        "ContainedObjects": [{"Name": "Custom_Model_Infinite_Bag", "Nickname": "Team token"}],
    }
    target = tts_impl.write_token_bag_object("test-team", bag, tmp_path)
    assert target.relative_to(tmp_path).as_posix() == "test-team/tts_objects/test-team-token-bag.json"
    assert json.loads(target.read_text(encoding="utf-8")) == {"ObjectStates": [bag]}
    timestamp = target.stat().st_mtime_ns
    assert tts_impl.write_token_bag_object("test-team", bag, tmp_path).stat().st_mtime_ns == timestamp

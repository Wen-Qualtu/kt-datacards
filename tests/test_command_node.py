import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

from pipeline.steps import extract_stats, generate_tts, tts_impl
from pipeline.utils.ktui_model_script import compose_command_node_loader, compose_ktui_model_script
from tools.build_command_node import ROOT, SCRIPT, build_save
from tools.check_gmnotes_parity import BASELINE, gmnotes_manifest

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


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua parity")
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
        team = extract_stats.prepare_team_data(json.loads(team_path.read_text(encoding="utf-8")), rules)
        cards = embedded_card_data(json.loads(box_path.read_text(encoding="utf-8")))
        for operative in team["datacards"]:
            if operative["name"] not in cards:
                continue
            expected = dict(cards[operative["name"]])
            expected.pop("description", None)
            cases.append({"operative": operative, "rules": {}, "expected": expected})

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


def test_prepared_fields_reuse_card_loadouts_without_mutating_source():
    team_path = ROOT / "output" / "blades-of-khaine" / "data" / "blades-of-khaine-team-data.json"
    box_path = ROOT / "output" / "blades-of-khaine" / "tts_objects" / "Blades Of Khaine.json"
    team = json.loads(team_path.read_text(encoding="utf-8"))
    box = json.loads(box_path.read_text(encoding="utf-8"))
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    original_team = json.loads(json.dumps(team))
    enriched = extract_stats.prepare_team_data(team, rules)
    expected = embedded_card_data(box)

    assert team == original_team
    assert "node_weapon_rules" not in enriched
    assert enriched["model_data_version"] == 1
    assert all("selection" not in item for item in enriched.get("operatives_selection", []))
    for original, operative in zip(team["datacards"], enriched["datacards"]):
        assert "node" not in operative
        model = expected[original["name"]]
        assert operative.get("selection") == model.get("selection")
        assert operative["stats"] == model["stats"]
        assert [weapon["type"] for weapon in operative["weapons"]] == [
            "melee" if weapon["name"].startswith("[F4641D]M[-]") else "ranged"
            for weapon in model["weapons"]
        ]
        resolved = {}
        for weapon in operative["weapons"]:
            resolved.update(weapon["weapon_rules"])
        assert resolved == model["weapon_rules"]
        for key in ("name", "apl", "movement", "save", "wounds", "base_size"):
            assert operative.get(key) == original.get(key)


def test_canoptek_warrior_and_crawler_loadout_options_are_precomputed():
    team = json.loads((ROOT / "output/canoptek-circle/data/canoptek-circle-team-data.json").read_text(encoding="utf-8"))
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    team = extract_stats.prepare_team_data(team, rules)
    nodes = {
        operative["name"]: operative["selection"]
        for operative in team["datacards"]
        if operative["name"] in {"CANOPTEK MACROCYTE WARRIOR", "CANOPTEK TOMB CRAWLER"}
    }

    assert [option["label"] for option in nodes["CANOPTEK MACROCYTE WARRIOR"]["groups"][0]] == [
        "Gauss scalpel; claws and tail", "Tesla caster; claws and tail"
    ]
    assert [option["label"] for option in nodes["CANOPTEK TOMB CRAWLER"]["groups"][0]] == [
        "Twin gauss reapers; claws", "Transdimensional isolator; claws"
    ]


def test_all_prepared_team_data_preserves_exact_serialized_gmnotes():
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert len(expected["teams"]) == 48
    assert sum(map(len, expected["teams"].values())) == 453
    assert gmnotes_manifest(prepared=True) == expected


def test_preparation_is_idempotent_and_cards_do_not_reclassify(monkeypatch):
    team = json.loads((ROOT / "output/angels-of-death/data/angels-of-death-team-data.json").read_text(encoding="utf-8"))
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    prepared = extract_stats.prepare_team_data(team, rules)
    assert extract_stats.prepare_team_data(prepared, rules) == prepared

    def unexpected(*args, **kwargs):
        pytest.fail("Prepared card serialization repeated upstream weapon or selection processing")

    monkeypatch.setattr(tts_impl, "_classify_weapon", unexpected)
    monkeypatch.setattr(tts_impl, "_match_weapon_rules", unexpected)
    monkeypatch.setattr(tts_impl, "_build_selection_for_gmnotes", unexpected)
    for operative in prepared["datacards"]:
        expected = tts_impl._build_gm_notes(operative, prepared, {})
        assert expected["stats"] == operative["stats"]
        assert expected["weapon_rules"]


@pytest.mark.parametrize("team_path", sorted((ROOT / "output").glob("*/data/*-team-data.json")),
                         ids=lambda path: path.parent.parent.name)
def test_real_card_embedding_keeps_gmnotes_and_lua_exactly_unchanged(team_path, tmp_path):
    raw = json.loads(team_path.read_text(encoding="utf-8"))
    rules = json.loads((CONFIG / "weapon_rules.json").read_text(encoding="utf-8"))
    prepared = extract_stats.prepare_team_data(raw, rules)
    slug = raw["team"]
    target = tmp_path / slug / "data" / team_path.name
    target.parent.mkdir(parents=True)
    original_cards = [{"CardID": 1000 + index, "Nickname": operative["name"]}
                      for index, operative in enumerate(raw["datacards"])]
    before = {"ContainedObjects": json.loads(json.dumps(original_cards))}
    after = {"ContainedObjects": json.loads(json.dumps(original_cards))}
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    assert tts_impl.embed_datacard_stats(before, slug, tmp_path, CONFIG)
    target.write_text(json.dumps(prepared, ensure_ascii=False), encoding="utf-8")
    assert tts_impl.embed_datacard_stats(after, slug, tmp_path, CONFIG)
    expected_hashes = json.loads(BASELINE.read_text(encoding="utf-8"))["teams"][slug]
    for legacy, current in zip(before["ContainedObjects"], after["ContainedObjects"]):
        assert current["GMNotes"] == legacy["GMNotes"], (slug, current["Nickname"])
        assert current["LuaScript"] == legacy["LuaScript"], (slug, current["Nickname"])
        assert hashlib.sha256(current["GMNotes"].encode("utf-8")).hexdigest() == expected_hashes[current["Nickname"]]


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
    enriched = extract_stats.prepare_team_data(team, rules)
    target = tmp_path / "warpcoven-team-data.json"
    assert extract_stats._save_stable(enriched, target)
    timestamp = target.stat().st_mtime_ns
    original_bytes = target.read_bytes()
    result = json.loads(target.read_text(encoding="utf-8"))

    assert result["team"] == "warpcoven"
    assert result["model_data_version"] == 1
    assert "node_weapon_rules" not in result
    assert all("node" not in card and "stats" in card for card in result["datacards"])
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
    assert "function ktCommandNodeAddCounters" not in node
    assert len(node.encode("utf-8")) < 60_000


def test_shared_helper_includes_composed_model_and_card_loader():
    helper = compose_command_node_loader(CONFIG)

    assert "KTUI_MODELSCRIPT_VERSION" in helper
    assert "function diffAndApply" in helper
    assert "function rebuildDescription" in helper
    assert "function onLoad" in helper
    assert "NODE_COUNTER_SETUP" in helper
    assert "function ktCommandNodeAddCounters" in helper
    assert "Gore Tank" in helper
    setup = json.loads(helper.split("NODE_COUNTER_SETUP = [====[", 1)[1].split("]====]", 1)[0])
    assert setup["angels-of-death"]["name"] == "Chapter Tactics"
    assert setup["angels-of-death"]["kind"] == "choice"
    assert setup["angels-of-death"]["select"] == 2
    assert len(setup["angels-of-death"]["options"]) == 8
    assert setup["goremongers"]["kind"] == "counter"
    assert setup["exodite-dragon-masters"]["kind"] == "counter"
    assert setup["exodite-dragon-masters"]["name"] == "Exodite Counters"
    assert setup["chaos-cult"]["applies_to"] == ["MUTANT", "TORMENT"]
    assert setup["chaos-cult"]["operative_select_count"] == {"MUTANT": 1, "TORMENT": 2}
    scripts = CONFIG / "defaults" / "tts-script"
    assert (scripts / "move-tool.lua").read_text(encoding="utf-8") in helper
    assert (scripts / "sprint-movement-tool.lua").read_text(encoding="utf-8") in helper


def test_pipeline_shared_loader_matches_existing_composition(tmp_path):
    target = tts_impl.write_command_node_loader(CONFIG, tmp_path)
    assert target.read_text(encoding="utf-8") == compose_command_node_loader(CONFIG)
    timestamp = target.stat().st_mtime_ns
    assert tts_impl.write_command_node_loader(CONFIG, tmp_path).stat().st_mtime_ns == timestamp


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua counter integration")
def test_remote_exodite_counters_filter_models_and_preserve_values():
    script = compose_command_node_loader(CONFIG) + r'''
Wait = {frames = function(callback) callback() end}
Color = {Green = {}, Orange = {}, Red = {}, White = {}}
function broadcastToColor() end
JSON = {decode = function(value) return value end, encode = function(value) return value end}
for _, mounted in ipairs({true, false}) do
    local installed = KTUI_MODELSCRIPT .. "\n" .. MOVE_TOOL_CODE
    local model = {script_state = {info = {categories = mounted and {"MOUNTED"} or {"DRAKOLITHE"}},
        owner = "existing-owner", kt_front = 90}, reloads = 0}
    model.getLuaScript = function() return installed end
    model.setLuaScript = function(value) installed = value end
    model.reload = function() model.reloads = model.reloads + 1 end
    local params = {team = "exodite-dragon-masters", model = model, playerColor = "White"}
    assert(ktCommandNodeAddCounters(params))
    assert(model.script_state.operative_counter_speed.current == 1)
    assert(installed:find('offsetXY="0 -10"', 1, true)
        or installed:find('offsetXY="0.0 -10"', 1, true))
    if mounted then
        assert(model.script_state.operative_counter_movement_remaining.current == 12)
        assert(model.script_state.operative_counter_remaining_actions.current == 4)
        assert(installed:find('id="ktcnid-status-oc-movement_remaining"', 1, true))
        assert(installed:find('id="ktcnid-status-oc-remaining_actions"', 1, true))
        model.script_state.operative_counter_movement_remaining.current = 7
    else
        assert(not model.script_state.operative_counter_movement_remaining)
        assert(not model.script_state.operative_counter_remaining_actions)
        assert(not installed:find('id="ktcnid-status-oc-movement_remaining"', 1, true))
        assert(not installed:find('id="ktcnid-status-oc-remaining_actions"', 1, true))
    end
    model.script_state.operative_counter_speed.current = 3
    assert(ktCommandNodeAddCounters(params))
    assert(model.script_state.operative_counter_speed.current == 3)
    if mounted then assert(model.script_state.operative_counter_movement_remaining.current == 7) end
    assert(model.script_state.owner == "existing-owner" and model.script_state.kt_front == 90)
    assert(model.reloads == 2)
    local marker = 'id="ktcnid-status-oc-speed"'
    local first = assert(installed:find(marker, 1, true))
    assert(not installed:find(marker, first + #marker, true))
    assert(load((installed:gsub("!=", "~="))))
end
print("exodite counter integration passed")
'''
    result = subprocess.run(
        [shutil.which("npx"), "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=script, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == "exodite counter integration passed", result.stderr
    assert not result.stderr


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua geometry integration")
def test_command_node_oval_ring_follows_calibrated_front():
    script = compose_command_node_loader(CONFIG) + r'''
Color = setmetatable({}, {__call = function() return {} end})
local scale = {x = 1.7, y = 0.4, z = 2.3}
self = {
    clearContextMenu = function() end,
    addContextMenuItem = function() end,
    getScale = function() return scale end,
    getBoundsNormalized = function() return {size = {x = 1, y = 1, z = 1}} end,
}
assert(load((KTUI_MODELSCRIPT:gsub("!=", "~="))))()
for _, headings in ipairs({{0, 90}, {90, 0}, {180, 270}, {40, 170}}) do
    local target, modelHeading = headings[1], headings[2]
    state = {base = {x = 42, z = 75}, kt_node_ui = true, kt_front = (target - modelHeading) % 360}
    local points = getCircleVectorPoints(0, 0.2, 64)
    local point = points[17]
    local horizontal, depth = point.x * scale.x, point.z * scale.z
    local yaw = math.rad(modelHeading)
    local worldX = horizontal * math.cos(yaw) + depth * math.sin(yaw)
    local worldZ = -horizontal * math.sin(yaw) + depth * math.cos(yaw)
    assert(math.abs(worldX - (75 / 2 / 25.4) * math.sin(math.rad(target))) < 0.001)
    assert(math.abs(worldZ - (75 / 2 / 25.4) * math.cos(math.rad(target))) < 0.001)
    assert(math.abs(point.y * scale.y - 0.2) < 0.001)
end
state = {base = {x = 32, z = 32}, kt_node_ui = true, kt_front = 90}
local round = getCircleVectorPoints(0, 0.2, 64)
assert(math.abs(round[1].x * scale.x - 16 / 25.4) < 0.001 and round[1].z == 0)
state = {base = {x = 42, z = 75}, kt_front = 90}
local stock = getCircleVectorPoints(0, 0.2, 64)
assert(math.abs(stock[1].x * scale.x - 21 / 25.4) < 0.001 and stock[1].z == 0)
print("front-aware oval geometry passed")
'''
    result = subprocess.run(
        [shutil.which("npx"), "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=script, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == "front-aware oval geometry passed", result.stderr
    assert not result.stderr


def test_oval_renderer_is_only_in_command_node_model_scripts():
    shared = compose_ktui_model_script(CONFIG)
    node_loader = compose_command_node_loader(CONFIG)
    assert "nodeGetCircleVectorPoints" not in shared
    assert "nodeGetCircleVectorPoints" in node_loader


def test_targeting_cone_is_embedded_instead_of_fetched():
    shared = compose_ktui_model_script(CONFIG)
    assert "KTMT%20Target%20Cone.lua" not in shared
    assert "ktLocalScript(KT_TARGET_CONE_CODE, function(req)" in shared
    assert (CONFIG / "defaults" / "tts-script" / "ktui-target-cone.lua").read_text(encoding="utf-8") in shared


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua geometry integration")
def test_targeting_lines_draw_on_selection_before_the_cone_is_moved():
    from tools.build_test_node import targeting_code

    script = "Color = function() return {} end\nmath.atan2 = math.atan2 or math.atan\n" + targeting_code() + r'''
local function model(x, z, bottom)
    bottom = bottom or 1
    return {
        getPosition = function() return {x = x, y = bottom, z = z} end,
        getRotation = function() return {y = 0} end,
        getTable = function() return {base = {x = 32, z = 32}} end,
        getBounds = function() return {offset = {y = 0}, center = {y = bottom + 0.25}, size = {y = 0.5}} end,
    }
end
local shooter, target = model(10, 10), model(10, 18)
local pos, lines, label = {x = 0, y = 2, z = 0}, nil, nil
local coroutineStarts = 0
getObjectFromGUID = function(guid)
    assert(guid == "shooter", "origin must be embedded before the cone script loads")
    return shooter
end
local env = setmetatable({}, {__index = _G})
startLuaCoroutine = function(_, name)
    coroutineStarts = coroutineStarts + 1
    local co = coroutine.create(env[name])
    local ok, err = coroutine.resume(co)
    assert(ok, err)
end
Physics = {cast = function() return {} end}
getAllObjects = function() return {} end
local hudText
Global = {UI = {getXml = function() return "ktmove_hud" end,
    setAttribute = function() end, setValue = function(_, text) hudText = text end}}
function broadcastToColor() end
local cone = {
    setName = function() end, clearButtons = function() end,
    createButton = function() end, setTags = function() end,
    getPosition = function() return pos end,
    setPosition = function(p) pos = p end,
    setVelocity = function() end, setAngularVelocity = function() end,
    setRotation = function() end,
    setVectorLines = function(value) lines = value end,
    editButton = function(button) label = button.label end,
}
env.self = cone
cone.setCustomObject = function() end
cone.setVar = function(name, value) env[name] = value end
cone.setLuaScript = function(source)
    assert(load(source, "target cone", "t", env))()
    env.onLoad("")
end
local callbacks = {}
Wait = {frames = function(fn, frames)
    assert(frames == 1, "loader should install the cone on the next frame")
    callbacks[#callbacks + 1] = fn
end}
local function nextFrame()
    local queued = callbacks
    callbacks = {}
    for _, fn in ipairs(queued) do fn() end
end
local function selectTarget(obj)
    env.onNumberTyped("Red", 1)
    env.onObjectPickUp("Red", obj)
    assert(#callbacks == 0, "selection draws immediately without a deferred callback")
end
self = {getGUID = function() return "shooter" end}
spawnObject = function(params)
    assert(params.position[1] == 0 and params.position[2] == 2, "original spawn location")
    return cone
end
agregaCono()
assert(#callbacks == 1, "model schedules cone installation")
nextFrame()
assert(coroutineStarts == 0, "loading must position the cone without starting a drag")
local radius = 16 * env.mtoi
assert(math.abs((pos.x - 10)^2 + (pos.z - 10)^2 - radius^2) < 1e-6,
    "spawning places the cone on the shooter base before target selection")
assert(pos.y == 1.5, "spawning sets origin height")
assert(lines == nil, "no target lines before selection")
selectTarget(target)
assert(env.objModel == shooter and env.ObjMiniTarget == target, "selection resolves both models")
assert(lines and #lines[1].points == 3, "selection draws lines without moving the cone")
assert(label == "7''", "selection refreshes range")
-- Retargeting must redraw immediately too.
lines = nil
selectTarget(model(10, 22))
assert(lines and label == "11''", "retargeting refreshes lines and range")
env.pickedUp = true
selectTarget(model(10, 12.5))
assert(env.tooCloseState and hudText == 'Target within 2" - all cover is ignored',
    "selection forces analysis even between throttled drag frames")
env.pickedUp = false
selectTarget(model(10, 18, 3))
assert(hudText == "No cover", "installed cone checks cover for a raised target on selection: " .. tostring(hudText))
assert(coroutineStarts == 0, "selection never requires a cone drag")
selectTarget(model(10, 22))
env.onPickUp("Red")
assert(env.pickedUp and coroutineStarts == 1, "dragging still starts normally")
env.onDropped("Red")
assert(not env.pickedUp and lines, "dropping retains the lines")
print("target selection lifecycle passed")
'''
    result = subprocess.run(
        [shutil.which("npx"), "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=script, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == "target selection lifecycle passed", result.stderr
    assert not result.stderr


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua geometry integration")
def test_targeting_lines_touch_the_outer_points_of_an_oval_target():
    cone = (CONFIG / "defaults" / "tts-script" / "ktui-target-cone.lua").read_text(encoding="utf-8")
    script = "Color = function() return {} end\nmath.atan2 = math.atan2 or math.atan\n" + cone + r'''
local function model(x, z, rotY, st)
    return {
        getPosition = function() return {x = x, y = 1, z = z} end,
        getRotation = function() return {x = 0, y = rotY, z = 0} end,
        getTable = function() return st end,
        getBounds = function() return {offset = {y = 0}, center = {y = 1.25}, size = {y = 0.5}} end,
    }
end
Physics = {cast = function() return {} end}
getAllObjects = function() return {} end
local lines, label
local conePos = {x = 0, y = 1, z = 0}
self = {
    getPosition = function() return conePos end,
    getBounds = function() return {offset = {y = 0}} end,
    setVectorLines = function(l) lines = l end,
    editButton = function(b) label = b.label end,
}
local mm = 0.0393701
-- {target x, z, rotY, state, heading the long axis should run along}
local cases = {
    {6, 0, 0, {base = {x = 42, z = 75}}, 0},
    {5, 4, 30, {base = {x = 42, z = 75}}, 30},
    {-3, 7, 90, {base = {x = 42, z = 75}, kt_node_ui = true, kt_front = 45}, 135},
    {4, -5, 200, {base = {x = 42, z = 75}, kt_front = 90}, 200},
    {5, 0, 0, {base = {x = 32, z = 32}}, 0},
}
for i, c in ipairs(cases) do
    local tx, tz, rotY, st, heading = c[1], c[2], c[3], c[4], c[5]
    ObjMiniTarget = model(tx, tz, rotY, st)
    objModel = model(-0.63, 0, 0, {base = {x = 32, z = 32}})
    estado_cono = 2
    refrescaVectores()
    local pts = lines[1].points
    local center = math.atan2(tx, tz)
    local function rel(a) return (a - center + math.pi) % (2 * math.pi) - math.pi end
    local h = math.rad(heading)
    local a, b = st.base.x * mm / 2 - 0.02, st.base.z * mm / 2 - 0.02
    local lo, hi, gap = math.huge, -math.huge, math.huge
    for k = 0, 19999 do
        local t = k * 2 * math.pi / 20000
        local u, v = a * math.cos(t), b * math.sin(t)
        local x = tx + u * math.cos(h) + v * math.sin(h)
        local z = tz - u * math.sin(h) + v * math.cos(h)
        local ang = rel(math.atan2(x, z))
        lo, hi = math.min(lo, ang), math.max(hi, ang)
        local fu, fv = (a + 0.02) * math.cos(t), (b + 0.02) * math.sin(t)
        local fx = tx + fu * math.cos(h) + fv * math.sin(h)
        local fz = tz - fu * math.sin(h) + fv * math.cos(h)
        gap = math.min(gap, math.sqrt((fx + 0.63) ^ 2 + fz ^ 2) - 16 * mm)
    end
    local e1, e2 = rel(math.atan2(pts[1].x, pts[1].z)), rel(math.atan2(pts[3].x, pts[3].z))
    assert(math.abs(math.max(e1, e2) - hi) < 1e-3, "case " .. i .. " upper tangent")
    assert(math.abs(math.min(e1, e2) - lo) < 1e-3, "case " .. i .. " lower tangent")
    assert(pts[2].x == 0 and pts[2].z == 0, "case " .. i .. " apex")
    assert(label == math.ceil(gap) .. "''", "case " .. i .. " range " .. label .. " vs " .. gap)
end
print("oval targeting passed")
'''
    result = subprocess.run(
        [shutil.which("npx"), "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=script, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == "oval targeting passed", result.stderr
    assert not result.stderr


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua geometry integration")
def test_targeting_lines_show_cover_and_obscured_from_terrain():
    cone = (CONFIG / "defaults" / "tts-script" / "ktui-target-cone.lua").read_text(encoding="utf-8")
    script = "Color = function() return {} end\nmath.atan2 = math.atan2 or math.atan\n" + cone + r'''
local function model(x, z, bottom)
    bottom = bottom or 1
    return {
        getPosition = function() return {x = x, y = bottom, z = z} end,
        getRotation = function() return {x = 0, y = 0, z = 0} end,
        getTable = function() return {base = {x = 32, z = 32}} end,
        getBounds = function() return {offset = {y = 0}, center = {y = bottom + 0.25}, size = {y = 0.5}} end,
    }
end
local function terrain(name, z1, z2, opts)
    opts = opts or {}
    local set = {}
    for _, t in ipairs(opts.tags or {}) do set[t] = true end
    local o = {type = opts.kind or "Generic", minX = opts.minX or -3, maxX = opts.maxX or 3, minZ = z1, maxZ = z2,
        minY = 0, maxY = opts.top or 3,
        getName = function() return name end, getDescription = function() return opts.description or "" end,
        getGUID = function() return name .. z1 end,
        hasTag = function(t) return set[t] == true end, getTags = function() return opts.tags or {} end}
    o.getPosition = function()
        -- originAtEnd: like the Tomb World doors, whose mesh origin is at one end
        return {x = opts.originAtEnd and o.minX or (o.minX + o.maxX) / 2, y = 0, z = (o.minZ + o.maxZ) / 2}
    end
    o.getBounds = function() return {center = {x = (o.minX + o.maxX) / 2, y = (o.minY + o.maxY) / 2, z = (o.minZ + o.maxZ) / 2},
        size = {x = o.maxX - o.minX, y = o.maxY - o.minY, z = o.maxZ - o.minZ}} end
    o.noCollider = opts.noCollider
    o.getRotation = function() return {x = 0, y = opts.rotY or 0, z = 0} end
    -- Unrotated size: x/z swap for a piece turned 90 degrees.
    o.getBoundsNormalized = function()
        local sx, sz = o.maxX - o.minX, o.maxZ - o.minZ
        if (opts.rotY or 0) % 180 == 90 then sx, sz = sz, sx end
        return {offset = {x = 0, y = 0, z = 0}, size = {x = sx, y = o.maxY - o.minY, z = sz}}
    end
    if opts.outline then
        o.script_code = '__bundle_register("base-board/hatchway", function refreshVectors()'
        local drawn = not opts.initiallyHidden
        o.getVectorLines = function() return drawn and {{points = opts.outline}} or {} end
        o.call = function(fn) assert(fn == "refreshVectors"); drawn = true; o.initialized = true end
        o.positionToWorld = function(p)
            local pos, h = o.getPosition(), math.rad(opts.rotY or 0)
            local x, z = p.x * (opts.scaleX or 1), p.z * (opts.scaleZ or 1)
            return {x = pos.x + x * math.cos(h) + z * math.sin(h), y = pos.y + p.y,
                z = pos.z - x * math.sin(h) + z * math.cos(h)}
        end
    end
    return o
end
-- Mock TTS ray: one hit per box, where the ray ENTERS it (none if it starts inside).
local boxes = {}
Physics = {cast = function(p)
    local o, d = p.origin, p.direction
    local m = math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z)
    local u = {x = d.x / m, y = d.y / m, z = d.z / m}
    local hits = {}
    for _, b in ipairs(boxes) do
        local lo, hi = -math.huge, math.huge
        local ok = not b.noCollider
        for _, ax in ipairs({{"x", b.minX, b.maxX}, {"y", b.minY, b.maxY}, {"z", b.minZ, b.maxZ}}) do
            local k, mn, mx = ax[1], ax[2], ax[3]
            if math.abs(u[k]) < 1e-12 then
                if o[k] < mn or o[k] > mx then ok = false end
            else
                local t1, t2 = (mn - o[k]) / u[k], (mx - o[k]) / u[k]
                lo, hi = math.max(lo, math.min(t1, t2)), math.min(hi, math.max(t1, t2))
            end
        end
        if ok and lo <= hi and lo > 0 and lo <= p.max_distance then
            hits[#hits + 1] = {hit_object = b.owner or b, point = {x = o.x + u.x * lo, y = o.y + u.y * lo, z = o.z + u.z * lo}}
        end
    end
    return hits
end}
local lines, label
local hud = {}
Color = setmetatable({fromString = function() return {lerp = function(c) return c end, toHex = function() return "FFFFFF" end} end,
    White = {}}, {__call = function() return {} end})
-- Like TTS: writes right after setXml are lost until the new XML has loaded.
local hudLoading = false
Global = {UI = {getXml = function() return "" end, setXml = function() hudLoading = true end,
    setAttribute = function(id, k, v) if not hudLoading then hud[id .. "." .. k] = v end end,
    setValue = function(id, v) if not hudLoading then hud[id] = v end end}}
Wait = {frames = function(fn) hudLoading = false; fn() end}
activeColor = "Red"
local conePosition = {x = 0, y = 1.5, z = 0.03}
self = {
    getPosition = function() return conePosition end,
    setPosition = function(position) conePosition = position end,
    setVelocity = function() end, setAngularVelocity = function() end,
    setRotation = function() end,
    setVectorLines = function(l) lines = l end,
    editButton = function(b) label = b.label end,
}
objModel = model(0, -0.6)
getObjectFromGUID = function() return objModel end
estado_cono = 2
colorLinea = "user"
getAllObjects = function() return boxes end
local function check(name, targetZ, pieces, cover, obscured)
    boxes = pieces
    estado_cono = 1
    onObjectPickUp("Red", model(0, targetZ))
    assert(coverState == cover, name .. ": cover " .. tostring(coverState))
    assert(obscuredState == obscured, name .. ": obscured " .. tostring(obscuredState))
    local want = cover == "heavy" and 0.1 or (cover == "light" and 0.55 or nil)
    if want then assert(lines[1].color[2] == want, name .. ": colour") else assert(lines[1].color == "user", name .. ": colour") end
    assert((lines[2] ~= nil) == obscured, name .. ": obscured arc")
    assert(label:find("^%d+''$"), name .. ": range-only label " .. label)
    assert(hud["ktmove_txt_Red.active"] == "true", name .. ": hud shown")
    assert((hud["ktmove_txt_Red"]:find("Obscured", 1, true) ~= nil) == obscured, name .. ": hud obscured")
end
check("clear", 8, {}, nil, false)
check("light near target", 8, {terrain("Light Rubble", 6.6, 6.8)}, "light", false)
check("light half way", 8, {terrain("Light Rubble", 4.0, 4.2)}, nil, false)
check("heavy half way", 8, {terrain("Heavy Wall", 4.0, 4.2)}, nil, true)
check("heavy near target", 8, {terrain("Heavy Wall", 6.6, 6.8)}, "heavy", false)
check("thick heavy", 8, {terrain("Heavy Block", 3.0, 6.8)}, "heavy", true)
check("heavy near shooter", 8, {terrain("Heavy Wall", 0.4, 0.7)}, nil, false)
check("heavy beats light", 8, {terrain("Light Rubble", 6.6, 6.7), terrain("Heavy Wall", 6.9, 7.0)}, "heavy", false)
check("light in description", 8, {terrain("", 6.6, 6.8, {description = "Light terrain"})}, "light", false)
check("untyped is heavy", 8, {terrain("Crate", 6.6, 6.8)}, "heavy", false)
check("operatives ignored", 8, {terrain("Ork", 4.0, 6.8, {tags = {"KTUIMini"}})}, nil, false)
check("long terrain name", 8, {terrain("  Heavy Wall " .. string.rep("x", 8192) .. "  ", 6.6, 6.8)}, "heavy", false)
check("long no-cover name", 8, {terrain(" \tTeleport " .. string.rep("x", 8192) .. "\n  ", 6.6, 6.8)}, nil, false)
check("within 2 inches", 2.5, {terrain("Light Rubble", 1.0, 1.2)}, nil, false)
local function solid(name, x1, x2, z1, z2, y1, y2)
    local o = terrain(name, z1, z2, {minX = x1, maxX = x2, top = y2})
    o.minY = y1
    return o
end
-- A low barricade near the target blocks a level shot.
check("portable barricade, level shot", 8, {solid("Portable barricade", -2, 2, 6.5, 6.8, 1, 1.3)}, "light", false)
check("heavy barricade", 8, {solid("Heavy barricade", -2, 2, 6.5, 6.8, 1, 1.3)}, "heavy", false)
-- Vantage. The killzone floor is the table top (y = 1); a building is a solid
-- block up to its Vantage floor at y = 4 plus optional rampart boxes above it.
local tableTop = terrain("Table", -20, 20, {kind = "Surface", minX = -20, maxX = 20, top = 1})
local LARGE_RUIN = "Large Ruin\nA The upper level is Vantage terrain.\nB The upper rampart is Light terrain.\nAll other parts of it are Heavy terrain."
local STRONGHOLD = "Stronghold\nA The upper level(s) is Vantage terrain.\nAll other parts of it are Heavy terrain."
local function building(name, description, z1, z2, ramparts)
    local o = solid(name, -3, 3, z1, z2, 1, 4)
    o.getDescription = function() return description or "" end
    local list = {o}
    for _, r in ipairs(ramparts or {}) do
        list[#list + 1] = {owner = o, minX = -3, maxX = 3, minZ = r[1], maxZ = r[2], minY = 4, maxY = 5.5}
    end
    return list
end
local function scene(...)
    local all = {tableTop}
    for _, group in ipairs({...}) do for _, b in ipairs(group) do all[#all + 1] = b end end
    return all
end
local function vantage(name, shooter, target, pieces, cover, obscured, hudText)
    boxes, objModel, ObjMiniTarget = pieces, shooter, target
    refrescaVectores(true)
    assert(coverState == cover, name .. ": cover " .. tostring(coverState))
    assert(obscuredState == obscured, name .. ": obscured " .. tostring(obscuredState))
    if hudText then assert(hud["ktmove_txt_Red"] == hudText, name .. ": readout " .. hud["ktmove_txt_Red"]) end
end
local ground = model(0, -0.6)
-- Shot at from below (errata examples): the target's Vantage is Light cover,
-- its own Heavy walls neither give cover nor obscure...
vantage("from below: light from the Vantage", ground, model(0, 7.5, 4),
    scene(building("Large Ruin", LARGE_RUIN, 6, 10)), "light", false, "Light cover")
-- ...a Heavy rampart above the lines within its 1" makes it Heavy cover...
vantage("from below: heavy rampart", ground, model(0, 7.2, 4),
    scene(building("Stronghold", STRONGHOLD, 6, 10, {{6, 6.2}})), "heavy", false)
-- ...a Light one (large ruin) stays Light.
vantage("from below: light rampart", ground, model(0, 7.2, 4),
    scene(building("Large Ruin", LARGE_RUIN, 6, 10, {{6, 6.2}})), "light", false)
-- A separate wall below the target's floor isn't visible to it: no cover.
vantage("from below: wall under the floor", ground, model(0, 7.2, 4),
    scene(building("Heavy, Vantage", nil, 6.2, 10), {solid("Heavy Wall", -3, 3, 5.9, 6.1, 1, 3.9)}), "light", false)
-- Vantage to Vantage at the same height: the target's rampart decides.
local perched = model(0, -0.6, 4)
local home = building("Heavy, Vantage", nil, -2, 1)
vantage("vantage to vantage: light rampart", perched, model(0, 7.2, 4),
    scene(home, building("Large Ruin", LARGE_RUIN, 6, 10, {{6, 6.2}})), "light", false)
vantage("vantage to vantage: heavy rampart", perched, model(0, 7.2, 4),
    scene(home, building("Stronghold", STRONGHOLD, 6, 10, {{6, 6.2}})), "heavy", false)
-- A rampart of another building in between is Light: it doesn't obscure...
vantage("vantage to vantage: rampart between", perched, model(0, 7.2, 4),
    scene(home, building("Heavy, Vantage", nil, 3.2, 4, {{3, 3.2}}), building("Large Ruin", LARGE_RUIN, 6, 10, {{6, 6.2}})),
    "light", false)
-- ...but a full-height Heavy wall in between still does.
vantage("vantage to vantage: heavy wall between", perched, model(0, 7.2, 4),
    scene(home, {solid("Heavy Wall", -3, 3, 3, 3.2, 1, 5.5)}, building("Large Ruin", LARGE_RUIN, 6, 10, {{6, 6.2}})),
    "light", true)
-- Shooting down from Vantage: normal cover near the target.
vantage("down from vantage: light", perched, model(0, 8),
    scene(home, {terrain("Light Rubble", 6.6, 6.8)}), "light", false, "Light cover")
objModel = model(0, -0.6)
-- Equipment barricades: lines through the feet only (not across the panel) are
-- Exposed. The panel runs along z at x = 0.6; the lines here stay left of it.
local feet = terrain("Portable barricade", 6.2, 7.2, {minX = 0.45, maxX = 0.75, rotY = 90})
check("barricade feet only", 8, {feet}, nil, false)
boxes, ObjMiniTarget = {feet}, model(0.75, 8)
refrescaVectores(true)
assert(coverState == "light", "line across the barricade panel: light cover")
-- Both on the table itself: normal analysis.
objModel = model(0, -0.6)
check("level on a table", 8, {tableTop, terrain("Light Rubble", 6.6, 6.8)}, "light", false)
check("within 2 inches, explained", 2.5, {terrain("Heavy Wall", 1.0, 1.2)}, nil, false)
assert(hud["ktmove_txt_Red"] == "Target within 2\" - all cover is ignored", "2in readout: " .. hud["ktmove_txt_Red"])
-- Board-type custom models are terrain; game boards/mats (Board, >= 12" both ways) are not.
check("board-type terrain", 8, {terrain("Heavy", 6.6, 6.8, {kind = "Board"})}, "heavy", false)
check("board-type antenna", 8, {terrain("Antenna", 6.6, 6.8, {kind = "Board", description = "Light, Insignificant"})}, "light", false)
check("game mat ignored", 8, {terrain("matObjSurface", 3, 20, {kind = "Board", minX = -10, maxX = 10})}, nil, false)
-- Exposed pieces by name (start of the name only).
for _, n in ipairs({"Teleport pad", "Fire Steps", "Razor Wire", "Ladders"}) do
    check(n, 8, {terrain(n, 6.6, 6.8)}, nil, false)
end
check("ladder later in the name", 8, {terrain("Heavy, Vantage, Console: Insignificant / Ladder:  Heavy, Scalable", 6.6, 6.8, {kind = "Board"})}, "heavy", false)
check("objective-tagged G4 terrain", 8, {terrain("G4: Objective Marker", 6.6, 6.8, {tags = {"KT_Objective"}, description = "Light, Insignificant, Vantage"})}, "light", false)
-- The table's G4 marker isn't seen by sight rays; it is tested as a cylinder from its bounds.
local g4 = {tags = {"KT_Objective"}, description = "Light, Insignificant, Vantage", noCollider = true, minX = -0.9, maxX = 0.9}
check("G4 marker without a hit collider", 9, {terrain("G4: Objective Marker", 5.9, 7.7, g4)}, "light", false)
g4.minX, g4.maxX = 2.0, 3.8
check("G4 marker beside the lines", 9, {terrain("G4: Objective Marker", 5.9, 7.7, g4)}, nil, false)
-- Bounds that include the 3.68" control-range decal don't widen the marker
-- (capped at a 40mm base); a long rules description is fine.
local decal = {tags = {"KT_Objective"}, noCollider = true, minX = -0.24, maxX = 3.44,
    description = "Light, Insignificant, Vantage\n\n" .. string.rep("Beacon: this terrain feature provides Heavy. ", 400)}
check("G4 control-range bounds", 9, {terrain("G4: Objective Marker", 5.06, 8.74, decal)}, nil, false)
g4.minX, g4.maxX = -0.9, 0.9
-- The target stands inside the G4's control-range disc (part of its collider):
-- that is not standing on the marker, so the beacon still gives cover. Its
-- type is the description's first line, though the rules text says "Heavy".
local inRange = terrain("G4: Objective Marker", 5.76, 9.44, {tags = {"KT_Objective"},
    description = "Light, Insignificant, Vantage\n\nBeacon: this terrain feature provides the Heavy rule.",
    minX = -1.84, maxX = 1.84, top = 1.01})
inRange.minY = 1
check("target in the G4 control range", 9, {inRange}, "light", false)
check("objective token still ignored", 8, {terrain("Objective", 6.6, 6.8, {tags = {"KT_Objective"}})}, nil, false)
-- Open doors: lines through the outline the piece draws under its opening are
-- clear; lines through the wall either side still give cover.
local mm = 0.0393701
local function span(lo, hi)
    return {{x = lo, y = 0, z = -0.05}, {x = hi, y = 0, z = -0.05},
        {x = hi, y = 0, z = 0.05}, {x = lo, y = 0, z = 0.05}}
end
local doorway = span(-1.2, 1.2)
check("through an open door", 8, {terrain("Open Door 3", 6.6, 6.8, {outline = doorway})}, nil, false)
check("open door without an outline is a wall", 8, {terrain("Open Door 3", 6.6, 6.8)}, "heavy", false)
check("closed door outline is not an opening", 8, {terrain("Closed Door 3", 6.6, 6.8, {outline = doorway})}, "heavy", false)
-- The real Tomb World outline spans local x=24..59.3 mm from the piece's
-- end-placed origin, compensating for scale.
local outline = {{x = 24 * mm / 0.4, y = 0, z = 0},
    {x = 59.3 * mm / 0.4, y = 0, z = 0},
    {x = 59.3 * mm / 0.4, y = 0, z = 0.2},
    {x = 24 * mm / 0.4, y = 0, z = 0.2}}
local measured = terrain("Breached Wall 1", 4, 4.2,
    {originAtEnd = true, scaleX = 0.4, outline = outline, initiallyHidden = true})
local geometry = openingGeometry(measured)
assert(measured.initialized, "missing outline initialized")
assert(math.abs(geometry.lo - (-3 + 24 * mm)) < 1e-6, "outline start")
assert(math.abs(geometry.hi - (-3 + 59.3 * mm)) < 1e-6, "outline end")
check("measured off-centre breach obscures", 8, {measured}, nil, true)
local centered = {{x = -0.15, y = 0, z = 0}, {x = 0.15, y = 0, z = 0},
    {x = 0.15, y = 0, z = 0.1}, {x = -0.15, y = 0, z = 0.1}}
check("narrow measured opening obscures", 8, {terrain("Open Door", 4, 4.2, {outline = centered})}, nil, true)
local broad = {{x = -2, y = 0, z = 0}, {x = 2, y = 0, z = 0},
    {x = 2, y = 0, z = 0.1}, {x = -2, y = 0, z = 0.1}}
check("wide measured opening is clear", 8, {terrain("Open Door", 4, 4.2, {outline = broad})}, nil, false)
-- Gallowdark hatchway: a centred 35.4 x 6.1 outline (4 corners, drawn
-- open so only 3 sides show), on a mirrored (scaleX = -1) asset bundle.
local hx, hz = 35.4 / 2 * mm, 6.1 / 2 * mm
local hatchway = {{x = -hx, y = 0, z = hz}, {x = hx, y = 0, z = hz},
    {x = hx, y = 0, z = -hz}, {x = -hx, y = 0, z = -hz}}
local rotated = terrain("Open Hatchway", -3, 3,
    {minX = 2.9, maxX = 3.1, rotY = 90, scaleX = -1, outline = hatchway})
local rotatedGeometry = openingGeometry(rotated)
assert(math.abs(rotatedGeometry.lo + hx) < 1e-6 and math.abs(rotatedGeometry.hi - hx) < 1e-6,
    "rotated mirrored hatchway outline")
local angled = {{x = -2, y = 0, z = 0}, {x = 3, y = 0, z = 0},
    {x = 3, y = 0, z = 0.1}, {x = -2, y = 0, z = 0.1}}
boxes = {terrain("Open Door", 3, 7, {minX = -6, maxX = 6, outline = angled})}
ObjMiniTarget = model(4, 8)
analyseTerrain({x = 4, z = 8, a = 0.01, b = 0.01, h = 0}, {x = 0, z = 0.03})
assert(coverState == "heavy" and obscuredState, "angled line leaves opening before reaching target")
check("opening tests reset", 8, {}, nil, false)
-- Key 4 reports the result and what each terrain piece on the sight lines does.
local printed = {}
printToColor = function(text) printed[#printed + 1] = text end
boxes = {terrain("Open Door 3", 6.6, 6.8, {outline = doorway}), terrain("Objective", 4.0, 4.2, {tags = {"KT_Objective"}})}
onNumberTyped("Red", 4)
local out = table.concat(printed, "\n")
assert(out:find("Targeting: No cover", 1, true), "explain header: " .. out)
assert(out:find("Open Door 3: no cover, the line goes through the open doorway", 1, true), "explain opening: " .. out)
assert(not out:find("Objective", 1, true), "objective tokens are not listed: " .. out)
printed = {}
boxes = {terrain("Light Rubble", 6.6, 6.8), terrain("Heavy Wall", 4.0, 4.2), terrain("Teleport pad", 2.0, 2.2)}
onNumberTyped("Red", 4)
out = table.concat(printed, "\n")
assert(out:find("Targeting: Light cover  +  Obscured", 1, true), "explain result: " .. out)
assert(out:find("Light Rubble: light cover", 1, true), "explain cover: " .. out)
assert(out:find("Heavy Wall: obscures the target", 1, true), "explain obscured: " .. out)
assert(out:find("Teleport pad: no cover (exposed terrain)", 1, true), "explain exposed: " .. out)
check("closed door", 8, {terrain("Closed Door 3", 6.6, 6.8)}, "heavy", false)
ObjMiniTarget = model(2, 8)
boxes = {terrain("Open Hatchway", 6.6, 6.8, {outline = span(-1.35, 1.35)})}
refrescaVectores()
assert(coverState == "heavy", "beside the opening: wall gives cover")
-- Same wall turned 90 degrees, shot along x.
local conePos = self.getPosition
self.getPosition = function() return {x = -3.4, y = 1.5, z = 0} end
objModel = model(-4, 0)
boxes = {terrain("Breached Wall 1", -3, 3, {minX = 2.9, maxX = 3.1, rotY = 90, outline = span(-1.35, 1.35)})}
ObjMiniTarget = model(4, 0)
refrescaVectores()
assert(coverState == nil and not obscuredState, "rotated: through the breach")
ObjMiniTarget = model(4, 2.5)
refrescaVectores()
assert(coverState == "heavy", "rotated: beside the breach")
self.getPosition = conePos
ObjMiniTarget = model(0, 8)
local platform = solid("Heavy Walkway", -1, 1, 7.0, 9.0, 0, 2)
ObjMiniTarget = model(0, 8, 2)
boxes = {platform}
refrescaVectores()
assert(coverState == "heavy" and not obscuredState, "shooting up: target's platform intervenes")
-- Shooting down from a platform: the shooter's own terrain never counts.
local perch = solid("Heavy Walkway", -1, 1, -1.5, 0.3, 0, 2)
boxes = {perch}
objModel, ObjMiniTarget = model(0, -0.6, 2), model(0, 8)
refrescaVectores()
assert(coverState == nil and not obscuredState, "shooting down: own platform ignored")
-- Both up on separate platforms at the same height: neither counts.
boxes = {perch, platform}
ObjMiniTarget = model(0, 8, 2)
refrescaVectores()
assert(coverState == nil and not obscuredState, "same level: target's platform ignored")
objModel = model(0, -0.6)
assert(hud["ktmove_txt_Red"] == "No cover", "clear readout: " .. hud["ktmove_txt_Red"])
check("both shown", 8, {terrain("Heavy Block", 3.0, 6.8)}, "heavy", true)
assert(hud["ktmove_txt_Red"] == "Heavy cover  +  Obscured", "readout lists both")
onDestroy()
assert(hud["ktmove_txt_Red.active"] == "false", "hud hidden when the cone goes")
function broadcastToColor() end
local destroyed = false
self.destruct = function() destroyed = true end
onNumberTyped("Red", 1)
assert(estado_cono == 1, "1 selects a target")
local locked = lockEnabled
onNumberTyped("Red", 2)
assert(lockEnabled == not locked, "2 toggles the base lock")
onNumberTyped("Red", 3)
assert(destroyed, "3 finishes")
assert(tryRandomize == nil, "R is left free")
print("cover and obscured passed")
'''
    result = subprocess.run(
        [shutil.which("npx"), "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=script, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == "cover and obscured passed", result.stderr
    assert not result.stderr


def test_model_scripts_bundle_is_tagged_and_published(tmp_path):
    from pipeline.utils.ktui_model_script import compose_model_scripts_bundle
    bundle = compose_model_scripts_bundle(CONFIG)
    model = bundle["model"]
    assert model.startswith(f'KT_MODELSCRIPT_VERSION = "{bundle["version"]}"')
    order = [model.index(f"-- {edge} {tag} --") for tag in ("KT_MODELSCRIPT_V1", "KT_TARGETING_V1", "KT_EXTENSION_V1")
             for edge in ("START", "END")]
    assert order == sorted(order)
    assert bundle["move"].startswith("-- START KT_MOVE_TOOL_V1 --") and bundle["move"].endswith("-- END KT_MOVE_TOOL_V1 --")
    assert bundle["sprint"].startswith("-- START KT_SPRINT_TOOL_V1 --")
    target = tts_impl.write_ktui_model_scripts(CONFIG, tmp_path)
    assert json.loads(target.read_text(encoding="utf-8")) == bundle


@pytest.mark.skipif(not shutil.which("npx"), reason="npx is required for Lua integration")
def test_extender_board_stamps_our_script_with_movement_and_owner():
    from tools.build_ktui_extender import build_board
    board = build_board("main")
    assert "ktui-model-scripts.json" in board["LuaScript"] and "xSpaghettyx" not in board["LuaScript"]
    assert "onClick=\"ExtendUI\"" in board["XmlUI"]
    script = r"""
local downloads, broadcasts, waits = 0, {}, {}
WebRequest = {get = function(url, cb) downloads = downloads + 1; cb({text = "bundle"}) end}
JSON = {decode = function(text)
    if text == "bundle" then return {version = "v", model = "MODEL", move = "MOVE", sprint = "SPRINT"} end
    return text
end}
Wait = {frames = function(fn) fn() end, time = function(fn) table.insert(waits, fn) end}
function broadcastToAll(m) broadcasts[#broadcasts + 1] = m end
local function figurine(guid, state, kind)
    local m = {tag = kind or "Figurine", tags = {}, guid = guid, script_state = state}
    m.setLuaScript = function(s) m.script = s end
    m.reload = function() m.reloaded = (m.reloaded or 0) + 1; return m end
    m.addTag = function(t) m.tags[t] = true end
    m.hasTag = function(t) return m.tags[t] == true end
    m.getGUID = function() return guid end
    m.call = function(fn, arg) if fn == "setOwningPlayer" then m.owner = arg end end
    return m
end
local rider = figurine("r", {info = {categories = {"Exodite", "Mounted"}}})
local trooper = figurine("t", {info = {categories = {"Trooper"}}})
local tile = figurine("x", nil, "Tile")
self = {getPosition = function() return {0, 1, 0} end}
Physics = {cast = function() return {{hit_object = rider}, {hit_object = trooper}, {hit_object = tile}} end}
local said
local player = {steam_id = "123", broadcast = function(m) said = m end}
ExtendUI(player)
assert(rider.script == "MODEL\n\nSPRINT" and trooper.script == "MODEL\n\nMOVE", "movement by keyword")
assert(rider.tags.KTUIMini and rider.tags.KTUIMiniDatacard and rider.reloaded == 1, "tags + reload")
assert(rider.owner == "123" and trooper.owner == "123", "owner set")
assert(tile.script == nil, "only figurines")
assert(said == "Extended KT UI on 2 model(s)", said)
local npo = figurine("n", {})
npo.tags = {KTUIMini = true, Operative = true}
local objects = {n = npo}
function getObjectFromGUID(g) return objects[g] end
local bag = {hasTag = function(t) return t == "_NPO bag" end}
onObjectLeaveContainer(bag, npo)
assert(npo.script == nil and #waits == 1, "NPO waits for the original autoextender")
waits[1]()
assert(npo.script == "MODEL\n\nMOVE" and npo.owner == nil, "NPO extended without owner")
onObjectLeaveContainer({hasTag = function() return false end}, npo)
assert(#waits == 1, "other bags ignored")
assert(downloads == 1, "scripts downloaded once")
print("extender board passed")
"""
    lua = board["LuaScript"].replace("KT_SCRIPTS_URL", "KT_SCRIPTS_URL", 1) + "\n" + script
    result = subprocess.run(
        [shutil.which("npx"), "--yes", "--package=fengari-node-cli", "fengari", "-"],
        input=lua, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout.strip() == "extender board passed", result.stderr
    assert not result.stderr


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


def test_standalone_token_bag_mirrors_mesh_into_collider(tmp_path):
    mesh = {"MeshURL": "https://example/token.obj?v=1", "ColliderURL": ""}
    bag = {"Name": "Custom_Model_Bag", "ContainedObjects": [{"CustomMesh": mesh}]}
    target = tts_impl.write_token_bag_object("test-team", bag, tmp_path)
    written = json.loads(target.read_text(encoding="utf-8"))["ObjectStates"][0]
    assert written["ContainedObjects"][0]["CustomMesh"]["ColliderURL"] == "https://example/token.obj?v=1"
    assert mesh["ColliderURL"] == ""

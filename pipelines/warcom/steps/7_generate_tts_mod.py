"""
Step 7: Generate TTS Command Node mod JSON

Takes an existing TTS workshop mod and adapts it to load
operative statlines from our roster.json files.
"""

import json
from pathlib import Path
from datetime import datetime
import logging
import argparse

logger = logging.getLogger(__name__)


# Simplified Lua script that loads from our JSON format
# This replaces the complex BattleScribe parsing
SIMPLE_LOADER_SCRIPT = """
-- KT Warcom Datacards Loader
-- Modified to use simple JSON roster format instead of BattleScribe

GITHUB_BASE_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/kt-datacards/main/output/"
CURRENT_ROSTER = nil

function onLoad()
    log("KT Warcom Datacards - Ready")
    createLoadButton()
end

function createLoadButton()
    self.createButton({
        click_function = "promptForTeam",
        label = "Load Team",
        position = {0, 0.2, 0},
        width = 1200,
        height = 400,
        font_size = 200
    })
end

function promptForTeam(obj, player_color, alt_click)
    -- Prompt player for team name
    broadcastToAll("Enter team name in chat (e.g. 'kommandos', 'pathfinders')", {r=0,g=0.7,b=1})
end

function onChat(message, player)
    -- Load team when player types team name
    if message:match("^[a-z%-]+$") then
        loadTeam(message)
        return false  -- Don't show message in chat
    end
end

function loadTeam(team_name)
    local url = GITHUB_BASE_URL .. team_name .. "/statlines/roster.json"
    broadcastToAll("Loading " .. team_name.. "...", {r=1,g=1,b=0})
    
    WebRequest.get(url, function(request)
        if request.is_error then
            broadcastToAll("Failed to load '" .. team_name .. "'. Check spelling.", {r=1,g=0,b=0})
            return
        end
        
        local data = JSON.decode(request.text)
        CURRENT_ROSTER = data
        displayRoster(data)
    end)
end

function displayRoster(roster)
    local msg = string.format("Loaded: %s (%d operatives)", 
        roster.team:gsub("%-", " "):upper(), roster.operative_count)
    broadcastToAll(msg, {r=0,g=1,b=0})
    
    -- Log operative summary
    log("=".. ("="):rep(60))
    log(string.format("Team: %s (Generated: %s)", roster.team, roster.generated))
    log("=".. ("="):rep(60))
    
    for i, op in ipairs(roster.operatives) do
        local weapons_count = op.weapons and #op.weapons or 0
        local rules_count = op.rules and #op.rules or 0
        
        log(string.format("[%d] %s", i, op.name))
        log(string.format("    APL:%s M:%s SV:%s W:%s | Weapons:%d Rules:%d",
            op.apl or "?", op.movement or "?", op.save or "?", op.wounds or "?",
            weapons_count, rules_count))
        
        if op.weapons then
            for j, w in ipairs(op.weapons) do
                local sr = w.special_rules and (" [" .. w.special_rules .. "]") or ""
                log(string.format("      - %s: A%s BS%s D%s%s", 
                    w.name, w.attacks or "?", w.hit or "?", w.damage or "?", sr))
            end
        end
        
        if op.rules then
            for j, r in ipairs(op.rules) do
                log(string.format("      * %s", r.name))
            end
        end
        log("")
    end
    
    -- TODO: Create operative models
    -- TODO: Assign data to models
end
"""


def generate_mod_from_template(template_file: Path, output_file: Path, 
                                github_username: str = "YOUR_USERNAME"):
    """Generate TTS mod by modifying existing workshop mod."""
    
    logger.info("Loading template mod: %s", template_file.name)
    
    # Load existing mod
    mod = json.loads(template_file.read_text(encoding='utf-8'))
    
    # Update metadata
    mod["SaveName"] = "KT Warcom Datacards"
    mod["Date"] = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
    mod["EpochTime"] = int(datetime.now().timestamp())
    mod["Note"] = "Operative statlines extracted from Warcom datacards"
    
    # Replace Lua script with simplified loader
    lua_script = SIMPLE_LOADER_SCRIPT.replace("YOUR_USERNAME", github_username)
    mod["LuaScript"] = lua_script
    
    # Clear tab states (remove BattleScribe data)
    if "TabStates" in mod:
        mod["TabStates"] = {}
    
    # Save new mod
    output_file.write_text(json.dumps(mod, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("✓ TTS mod saved: %s", output_file)
    return output_file


def generate_simple_mod(output_file: Path, github_username: str = "YOUR_USERNAME"):
    """Generate minimal TTS mod from scratch."""
    
    logger.info("Generating minimal TTS mod...")
    
    # Create a notecard object to hold the script
    notecard_object = {
        "Name": "Notecard",
        "Transform": {
            "posX": 0.0,
            "posY": 1.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 0.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": "KT Warcom Datacards",
        "Description": "Click 'Load Team' button or type team name in chat\\n\\nExamples: kommandos, pathfinders, blooded\\n\\nData loaded from Warcom datacards extraction",
        "ColorDiffuse": {
            "r": 1.0,
            "g": 1.0,
            "b": 1.0
        },
        "Locked": False,
        "Grid": True,
        "Snap": True,
        "Autoraise": True,
        "Sticky": True,
        "Tooltip": True,
        "GUID": "abc123",
        "LuaScript": SIMPLE_LOADER_SCRIPT.replace("YOUR_USERNAME", github_username),
        "LuaScriptState": ""
    }
    
    mod = {
        "SaveName": "KT Warcom Datacards",
        "Date": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"),
        "EpochTime": int(datetime.now().timestamp()),
        "VersionNumber": "v1.0",
        "GameMode": "KT Warcom",
        "GameType": "Utility",
        "GameComplexity": "Low Complexity",
        "Tags": ["Miniature Games", "Wargames", "Kill Team"],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "Table_Poker",
        "Sky": "Sky_Cathedral",
        "Note": "Loads operative data from Warcom datacards extraction",
        "Grid": {
            "Type": 0,
            "Lines": False,
            "Snapping": False,
            "xSize": 2.0,
            "ySize": 2.0
        },
        "Lighting": {
            "LightIntensity": 0.54,
            "AmbientIntensity": 1.3
        },
        "Hands": {
            "Enable": True
        },
        "LuaScript": "",
        "LuaScriptState": "",
        "ObjectStates": [notecard_object]
    }
    
    output_file.write_text(json.dumps(mod, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info("✓ TTS mod saved: %s", output_file)
    return output_file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    parser = argparse.ArgumentParser(description="Generate TTS mod for Warcom datacards")
    parser.add_argument("--template", type=Path, help="Existing TTS mod to use as template")
    parser.add_argument("--github-username", default="YOUR_USERNAME", help="GitHub username for data URLs")
    parser.add_argument("--output", type=Path, default=Path("output/kt-warcom-datacards.json"), 
                        help="Output mod file")
    
    args = parser.parse_args()
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    if args.template and args.template.exists():
        mod_file = generate_mod_from_template(args.template, args.output, args.github_username)
    else:
        mod_file = generate_simple_mod(args.output, args.github_username)
    
    print(f"\n✓ TTS Mod generated: {mod_file}")
    print("\nNext steps:")
    print("1. Update GitHub username in Lua script if needed")
    print("2. Push output/ folder to GitHub repository")
    print("3. Import into TTS: Games > Saved Objects > Save & Load > Import")
    print("4. In TTS, type team name in chat (e.g. 'kommandos', 'path finders')")


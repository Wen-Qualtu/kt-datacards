"""
Generate TTS update script with team list from config
"""
import yaml
from pathlib import Path

def load_team_config():
    """Load team configuration"""
    config_path = Path('config/team-config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config['teams']

def generate_team_list_lua(teams):
    """Generate Lua table with team canonical names"""
    lua_lines = ["local EXPECTED_TEAMS = {"]
    for team_id, team_data in sorted(teams.items()):
        canonical_name = team_data['canonical_name']
        lua_lines.append(f'  ["{canonical_name}"] = true,')
    lua_lines.append("}")
    return "\n".join(lua_lines)

def main():
    teams = load_team_config()
    team_count = len(teams)
    
    print(f"Found {team_count} teams in config")
    print("\nLua table to add to script:")
    print(generate_team_list_lua(teams))
    print(f"\nTotal teams: {team_count}")

if __name__ == '__main__':
    main()

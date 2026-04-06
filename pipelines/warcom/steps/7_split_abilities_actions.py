#!/usr/bin/env python3
"""
Split operative rules into abilities and unique actions based on AP cost.

Rules with (xAP) pattern are unique actions.
Rules without AP cost are abilities.
"""

import json
import re
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Pattern to detect unique actions: (1AP), (2AP), etc.
AP_COST_PATTERN = re.compile(r'\(\d+AP\)', re.IGNORECASE)


def split_abilities_and_actions(roster_data):
    """
    Split rules into passive_abilities and unique_actions for each operative.
    
    Returns updated roster data with new structure:
    - passive_abilities: rules without AP cost
    - unique_actions: rules with (xAP) pattern
    
    Also removes the legacy 'rules' and '_rules_temp' fields.
    """
    abilities_count = 0
    actions_count = 0
    edge_cases = []
    
    for operative in roster_data.get('operatives', []):
        # Get rules from either the old 'rules' field or temp field
        rules = operative.get('_rules_temp', []) or operative.get('rules', [])
        
        abilities = []
        unique_actions = []
        
        for rule in rules:
            rule_name = rule.get('name', '')
            
            # Skip empty rules
            if not rule_name or not rule_name.strip():
                continue
            
            # Check if it has AP cost pattern
            if AP_COST_PATTERN.search(rule_name):
                unique_actions.append(rule)
                actions_count += 1
            else:
                abilities.append(rule)
                abilities_count += 1
                
                # Flag potential edge cases (actions without AP cost)
                # Common action keywords that might be missing AP cost
                action_keywords = ['action', 'move', 'shoot', 'fight', 'dash', 'charge']
                if any(kw in rule_name.lower() for kw in action_keywords):
                    edge_cases.append({
                        'operative': operative.get('name'),
                        'rule': rule_name,
                        'source': operative.get('source_file')
                    })
        
        # Update operative with split fields
        operative['passive_abilities'] = abilities
        operative['unique_actions'] = unique_actions
        
        # Remove legacy fields
        if 'rules' in operative:
            del operative['rules']
        if '_rules_temp' in operative:
            del operative['_rules_temp']
    
    return roster_data, abilities_count, actions_count, edge_cases


def process_team(team_path: Path, force: bool = False):
    """Process a single team's roster.json."""
    roster_path = team_path / "statlines" / "roster.json"
    
    if not roster_path.exists():
        return None
    
    # Load existing roster
    with open(roster_path, 'r', encoding='utf-8') as f:
        roster_data = json.load(f)
    
    # Save original last_modified
    original_last_modified = roster_data.get('last_modified')
    
    # Split abilities and actions
    updated_data, abilities_count, actions_count, edge_cases = split_abilities_and_actions(roster_data)
    
    # Compute hash of new content (without timestamp to compare structural changes only)
    temp_data = updated_data.copy()
    temp_data.pop('last_modified', None)  # Remove timestamp for comparison
    new_content_json = json.dumps(temp_data, sort_keys=True, ensure_ascii=False)
    new_hash = hashlib.sha256(new_content_json.encode('utf-8')).hexdigest()
    
    # Compute hash of original content (without timestamp)
    temp_original = roster_data.copy()
    temp_original.pop('last_modified', None)
    old_content_json = json.dumps(temp_original, sort_keys=True, ensure_ascii=False)
    old_hash = hashlib.sha256(old_content_json.encode('utf-8')).hexdigest()
    
    # Check if anything changed
    if old_hash == new_hash and not force:
        logger.info("  ⊘ %s: No changes in abilities/actions split", team_path.name)
        return {
            'team': team_path.name,
            'abilities': abilities_count,
            'actions': actions_count,
            'edge_cases': edge_cases,
            'status': 'unchanged'
        }
    
    # Update last_modified timestamp only if changes detected or forced
    updated_data['last_modified'] = datetime.now(timezone.utc).isoformat()
    
    # Save updated roster
    with open(roster_path, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, indent=2, ensure_ascii=False)
    
    logger.info("  ✓ %s: Updated with %d abilities, %d actions", 
                team_path.name, abilities_count, actions_count)
    
    return {
        'team': team_path.name,
        'abilities': abilities_count,
        'actions': actions_count,
        'edge_cases': edge_cases,
        'status': 'updated'
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Split abilities and unique actions in roster.json files')
    parser.add_argument('--force', action='store_true', help='Force update even if no changes detected')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Split Abilities and Unique Actions")
    logger.info("=" * 60)
    
    output_dir = Path("output")
    team_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()])
    
    logger.info(f"Teams to process: {len(team_dirs)}")
    if args.force:
        logger.info("Mode: FORCE UPDATE")
    logger.info("")
    
    total_abilities = 0
    total_actions = 0
    all_edge_cases = []
    updated_count = 0
    unchanged_count = 0
    
    for team_dir in team_dirs:
        result = process_team(team_dir, force=args.force)
        
        if result:
            total_abilities += result['abilities']
            total_actions += result['actions']
            all_edge_cases.extend(result['edge_cases'])
            
            if result.get('status') == 'updated':
                updated_count += 1
            elif result.get('status') == 'unchanged':
                unchanged_count += 1
            
            if result['abilities'] > 0 or result['actions'] > 0:
                logger.info(
                    f"  {result['team']}: "
                    f"{result['abilities']} abilities, "
                    f"{result['actions']} actions"
                )
    
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Total abilities: {total_abilities}")
    logger.info(f"Total unique actions: {total_actions}")
    logger.info(f"Teams updated: {updated_count}")
    logger.info(f"Teams unchanged: {unchanged_count}")
    logger.info("=" * 60)
    
    # Report edge cases
    if all_edge_cases:
        logger.info("")
        logger.info("EDGE CASES - Abilities with action keywords (no AP cost):")
        logger.info(f"Found {len(all_edge_cases)} potential actions without AP cost")
        logger.info("")
        for case in all_edge_cases[:10]:  # Show first 10
            logger.info(f"  {case['operative']}: {case['rule']}")
            logger.info(f"    Source: {case['source']}")
        
        if len(all_edge_cases) > 10:
            logger.info(f"  ... and {len(all_edge_cases) - 10} more")
    
    logger.info("")
    logger.info("Updated all roster.json files with 'abilities' and 'unique_actions' fields")


if __name__ == "__main__":
    main()

"""Set all tokens to default stackable KTUI tags.

This script sets ALL tokens to ['KTUIStackable', 'KTUIToken'] regardless of their type.
After running this, update the config with correct marker types, then run a separate
script to set marker tokens to ['KTUIToken', 'KTUIMarker'].
"""

import json
from pathlib import Path


def fix_token_bag(token_bag_path: Path) -> bool:
    """Set all tokens in a standalone token bag to default stackable tags."""
    with open(token_bag_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False
    
    token_bag = data['ObjectStates'][0]
    infinite_bags = token_bag.get('ContainedObjects', [])
    
    for infinite_bag in infinite_bags:
        if infinite_bag.get('Name') != 'Custom_Model_Infinite_Bag':
            continue
        
        bag_nickname = infinite_bag.get('Nickname', '')
        if not bag_nickname:
            continue
        
        # Default tags for all tokens
        correct_tags = ['KTUIStackable', 'KTUIToken']
        
        # Remove KTUI tags from the bag itself
        current_bag_tags = infinite_bag.get('Tags', [])
        cleaned_bag_tags = [tag for tag in current_bag_tags if not tag.startswith('KTUI')]
        if current_bag_tags != cleaned_bag_tags:
            infinite_bag['Tags'] = cleaned_bag_tags
            modified = True
        
        # Update tags on contained tokens
        for token in infinite_bag.get('ContainedObjects', []):
            token_current_tags = token.get('Tags', [])
            if token_current_tags != correct_tags:
                token['Tags'] = correct_tags
                modified = True
                print(f"  Updated {bag_nickname}: {token_current_tags} -> {correct_tags}")
        
        # Update tags on child tokens
        for token in infinite_bag.get('ChildObjects', []):
            token_current_tags = token.get('Tags', [])
            if token_current_tags != correct_tags:
                token['Tags'] = correct_tags
                modified = True
    
    if modified:
        with open(token_bag_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return modified


def fix_cardbox(cardbox_path: Path) -> bool:
    """Set all tokens in a card box token bag to default stackable tags."""
    with open(cardbox_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    modified = False
    
    if not data.get('ObjectStates') or len(data['ObjectStates']) == 0:
        return False
    
    card_box = data['ObjectStates'][0]
    contained_objects = card_box.get('ContainedObjects', [])
    
    # Find the token bag
    for obj in contained_objects:
        nickname = obj.get('Nickname', '').lower()
        
        if 'token' in nickname and obj.get('Name') == 'Custom_Model_Bag':
            # Process all infinite bags inside the token bag
            infinite_bags = obj.get('ContainedObjects', [])
            for infinite_bag in infinite_bags:
                if infinite_bag.get('Name') != 'Custom_Model_Infinite_Bag':
                    continue
                
                bag_nickname = infinite_bag.get('Nickname', '')
                if not bag_nickname:
                    continue
                
                # Default tags for all tokens
                correct_tags = ['KTUIStackable', 'KTUIToken']
                
                # Remove KTUI tags from the bag itself
                current_bag_tags = infinite_bag.get('Tags', [])
                cleaned_bag_tags = [tag for tag in current_bag_tags if not tag.startswith('KTUI')]
                if current_bag_tags != cleaned_bag_tags:
                    infinite_bag['Tags'] = cleaned_bag_tags
                    modified = True
                
                # Update tags on contained tokens
                for token in infinite_bag.get('ContainedObjects', []):
                    token_current_tags = token.get('Tags', [])
                    if token_current_tags != correct_tags:
                        token['Tags'] = correct_tags
                        modified = True
                        print(f"  Updated {bag_nickname}: {token_current_tags} -> {correct_tags}")
                
                # Update tags on child tokens
                for token in infinite_bag.get('ChildObjects', []):
                    token_current_tags = token.get('Tags', [])
                    if token_current_tags != correct_tags:
                        token['Tags'] = correct_tags
                        modified = True
            
            break
    
    if modified:
        with open(cardbox_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return modified


def main():
    """Main function to set all tokens to default tags."""
    print("Setting ALL tokens to default stackable tags: ['KTUIStackable', 'KTUIToken']")
    print("=" * 60)
    
    tts_objects_dir = Path("tts_objects")
    
    # Process standalone token bags
    print("\nProcessing standalone token bags...")
    token_bag_files = list(tts_objects_dir.glob("*/*tokenbag.json"))
    token_bag_files = [f for f in token_bag_files if f.parent.name != 'tts_objects']
    
    modified_count = 0
    for token_bag_path in sorted(token_bag_files):
        team_slug = token_bag_path.parent.name
        print(f"\n{team_slug}:")
        
        was_modified = fix_token_bag(token_bag_path)
        if was_modified:
            modified_count += 1
            print(f"  ✓ Modified {token_bag_path.name}")
        else:
            print(f"  ✓ No changes needed")
    
    print(f"\nModified {modified_count} standalone token bags")
    
    # Process card boxes
    print("\n" + "=" * 60)
    print("Processing card box token bags...")
    cardbox_files = list(tts_objects_dir.glob("*/*Cards.json"))
    cardbox_files = [f for f in cardbox_files if f.parent.name != 'tts_objects']
    
    modified_count = 0
    for cardbox_path in sorted(cardbox_files):
        team_slug = cardbox_path.parent.name
        print(f"\n{team_slug}:")
        
        was_modified = fix_cardbox(cardbox_path)
        if was_modified:
            modified_count += 1
            print(f"  ✓ Modified {cardbox_path.name}")
        else:
            print(f"  ✓ No changes needed")
    
    print(f"\nModified {modified_count} card boxes")
    print("\n" + "=" * 60)
    print("Complete! All tokens now have default stackable tags.")
    print("Next: Update config with correct marker types, then run marker fix script.")


if __name__ == '__main__':
    main()

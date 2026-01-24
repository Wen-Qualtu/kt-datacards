"""
Update KT Display Manager buttons to 2x2 grid layout.
Top row: Self-Update | Reload Teams
Bottom row: Place on Table | Recall All Teams
"""

import json
from pathlib import Path


def update_button_layout():
    """Update the Manager bag buttons to 2x2 grid."""
    manager_path = Path("dev/examples/KT Display Manager.json")
    
    with open(manager_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    bag = data['ObjectStates'][0]
    xml_ui = bag['XmlUI']
    
    # Find and replace the button layout
    old_layout = '''        <HorizontalLayout spacing="50" 
                          childForceExpandWidth="true" 
                          childForceExpandHeight="false"
                          preferredHeight="140">
            <Button onClick="selfUpdate" 
                    minWidth="340" 
                    preferredHeight="140" 
                    fontSize="40"
                    color="#9C27B0"
                    textColor="#FFFFFF">Self-Update</Button>
            <Button onClick="refreshFromGitHub" 
                    minWidth="340" 
                    preferredHeight="140" 
                    fontSize="40"
                    color="#1976D2"
                    textColor="#FFFFFF">Reload Teams</Button>
            <Button onClick="placeTeamsOnTable" 
                    minWidth="340" 
                    preferredHeight="140" 
                    fontSize="40"
                    color="#388E3C"
                    textColor="#FFFFFF">Place on Table</Button>
            <Button onClick="recallTeamsToManager" 
                    minWidth="340" 
                    preferredHeight="140" 
                    fontSize="40"
                    color="#F57C00"
                    textColor="#FFFFFF">Recall All Teams</Button>
        </HorizontalLayout>'''
    
    new_layout = '''        <VerticalLayout spacing="20">
            <!-- Top Row: Update buttons -->
            <HorizontalLayout spacing="50" 
                              childForceExpandWidth="true" 
                              childForceExpandHeight="false"
                              preferredHeight="140">
                <Button onClick="selfUpdate" 
                        preferredHeight="140" 
                        fontSize="44"
                        color="#9C27B0"
                        textColor="#FFFFFF">Self-Update</Button>
                <Button onClick="refreshFromGitHub" 
                        preferredHeight="140" 
                        fontSize="44"
                        color="#1976D2"
                        textColor="#FFFFFF">Reload Teams</Button>
            </HorizontalLayout>
            <!-- Bottom Row: Place/Recall buttons -->
            <HorizontalLayout spacing="50" 
                              childForceExpandWidth="true" 
                              childForceExpandHeight="false"
                              preferredHeight="140">
                <Button onClick="placeTeamsOnTable" 
                        preferredHeight="140" 
                        fontSize="44"
                        color="#388E3C"
                        textColor="#FFFFFF">Place on Table</Button>
                <Button onClick="recallTeamsToManager" 
                        preferredHeight="140" 
                        fontSize="44"
                        color="#F57C00"
                        textColor="#FFFFFF">Recall All Teams</Button>
            </HorizontalLayout>
        </VerticalLayout>'''
    
    if old_layout in xml_ui:
        xml_ui = xml_ui.replace(old_layout, new_layout)
        bag['XmlUI'] = xml_ui
        
        with open(manager_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print("✓ Updated button layout to 2x2 grid")
        print("  Top row: Self-Update | Reload Teams")
        print("  Bottom row: Place on Table | Recall All Teams")
        print("  Font size increased back to 44 (more space per button)")
        return True
    else:
        print("⚠ Could not find button layout to update")
        return False


if __name__ == '__main__':
    print("Updating Manager bag button layout...\n")
    if update_button_layout():
        print("\n✓ Button layout updated successfully!")
    else:
        print("\n✗ Update failed")

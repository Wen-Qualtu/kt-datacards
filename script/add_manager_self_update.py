"""
Add self-update functionality to the KT Display Manager bag.
The bag will be able to update itself by spawning a new version from GitHub,
transferring all contents, and then destroying the old bag.
"""

import json
from pathlib import Path


def add_self_update_function():
    """Add self-update functionality to the Manager bag."""
    manager_path = Path("dev/examples/KT Display Manager.json")
    
    with open(manager_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    bag = data['ObjectStates'][0]
    lua_script = bag['LuaScript']
    
    # Add the Manager URL constant at the top
    old_constants = 'local TTS_BOXES_JSON_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-card-boxes.json"\r\nlocal isUpdating = false\r\nlocal positions = {}'
    
    new_constants = 'local TTS_BOXES_JSON_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-card-boxes.json"\r\nlocal MANAGER_METADATA_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/tts-manager.json"\r\nlocal isUpdating = false\r\nlocal positions = {}'
    
    lua_script = lua_script.replace(old_constants, new_constants)
    
    # Add self-update function before refreshFromGitHub
    self_update_function = '''
function selfUpdate()
    if isUpdating then
        broadcastToAll("Update already in progress...", {1, 0.5, 0})
        return
    end
    
    isUpdating = true
    broadcastToAll("Checking for Manager bag updates...", {0.2, 0.8, 1})
    
    -- Fetch manager metadata
    WebRequest.get(MANAGER_METADATA_URL, function(webReturn)
        if webReturn.is_error then
            broadcastToAll("Could not check for updates: " .. webReturn.error, {1, 0, 0})
            isUpdating = false
            return
        end
        
        local success, metadata = pcall(function() return JSON.decode(webReturn.text) end)
        if not success or not metadata.url then
            broadcastToAll("Could not parse update metadata", {1, 0, 0})
            isUpdating = false
            return
        end
        
        broadcastToAll("Fetching latest Manager bag...", {0.2, 0.8, 1})
        
        -- Add cache busting to force fresh download
        local cacheBust = metadata.last_modified and metadata.last_modified:gsub("[^0-9]", "") or math.random(1, 999999)
        local managerURL = metadata.url .. "?v=" .. cacheBust
        
        WebRequest.get(managerURL, function(managerReturn)
            if managerReturn.is_error then
                broadcastToAll("Could not fetch Manager update: " .. managerReturn.error, {1, 0, 0})
                isUpdating = false
                return
            end
            
            local success, managerData = pcall(function() return JSON.decode(managerReturn.text) end)
            if not success or not managerData.ObjectStates or #managerData.ObjectStates == 0 then
                broadcastToAll("Could not parse Manager data", {1, 0, 0})
                isUpdating = false
                return
            end
            
            broadcastToAll("Creating new Manager bag...", {0.2, 0.8, 1})
            
            -- Get my current position, rotation, and state
            local myPos = self.getPosition()
            local myRot = self.getRotation()
            local myState = self.script_state
            local myContents = self.getObjects()
            
            -- Spawn the new manager bag
            local newManagerData = managerData.ObjectStates[1]
            local newManager = spawnObjectJSON({
                json = JSON.encode(newManagerData),
                position = myPos + Vector(0, 5, 0)
            })
            
            Wait.condition(
                function()
                    -- Transfer state and position
                    newManager.script_state = myState
                    newManager.setPosition(myPos)
                    newManager.setRotation(myRot)
                    
                    broadcastToAll("Transferring " .. #myContents .. " team bags to new Manager...", {0.2, 0.8, 1})
                    
                    -- Transfer all contents to new bag
                    local transferred = 0
                    for i, item in ipairs(myContents) do
                        Wait.time(function()
                            local obj = self.takeObject({guid = item.guid, smooth = false})
                            Wait.condition(
                                function()
                                    newManager.putObject(obj)
                                    transferred = transferred + 1
                                    
                                    if transferred == #myContents then
                                        -- All transferred, destroy old bag
                                        Wait.time(function()
                                            broadcastToAll("✓ Manager bag updated successfully!", {0, 1, 0})
                                            self.destruct()
                                        end, 0.5)
                                    end
                                end,
                                function() return obj ~= nil and not obj.spawning end,
                                3
                            )
                        end, i * 0.1)
                    end
                    
                    -- If bag was empty, just destroy old one
                    if #myContents == 0 then
                        Wait.time(function()
                            broadcastToAll("✓ Manager bag updated successfully!", {0, 1, 0})
                            self.destruct()
                        end, 0.5)
                    end
                end,
                function() return newManager ~= nil and not newManager.spawning end,
                10,
                function()
                    broadcastToAll("Timeout spawning new Manager bag", {1, 0, 0})
                    isUpdating = false
                end
            )
        end)
    end)
end

'''
    
    # Insert before refreshFromGitHub function
    insert_point = 'function refreshFromGitHub()'
    lua_script = lua_script.replace(insert_point, self_update_function + insert_point)
    
    bag['LuaScript'] = lua_script
    
    # Update the XmlUI to add Self-Update button
    xml_ui = bag['XmlUI']
    
    # Add button before Reload All Teams
    old_buttons = '''            <Button onClick="refreshFromGitHub" 
                    minWidth="440" 
                    preferredHeight="140" 
                    fontSize="44"
                    color="#1976D2"
                    textColor="#FFFFFF">Reload All Teams</Button>'''
    
    new_buttons = '''            <Button onClick="selfUpdate" 
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
                    textColor="#FFFFFF">Reload Teams</Button>'''
    
    xml_ui = xml_ui.replace(old_buttons, new_buttons)
    
    # Adjust button widths for 4 buttons instead of 3
    xml_ui = xml_ui.replace('minWidth="440"', 'minWidth="340"')
    xml_ui = xml_ui.replace('fontSize="44"', 'fontSize="40"')
    
    bag['XmlUI'] = xml_ui
    
    # Save
    with open(manager_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print("✓ Added self-update functionality to Manager bag")
    print("  • New button: 'Self-Update' (purple)")
    print("  • Fetches latest version from GitHub")
    print("  • Transfers all contents to new bag")
    print("  • Destroys old bag")
    return True


if __name__ == '__main__':
    print("Adding self-update to KT Display Manager...\n")
    add_self_update_function()
    print("\n✓ Manager bag can now update itself!")

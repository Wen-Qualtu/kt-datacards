-- Bag of Boxes Reload Script
-- This script reloads team card boxes from the tts-card-boxes.json file
-- It fetches the JSON and spawns each team box

local DATACARDS_URLS_JSON_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/datacards-urls.json"

function onload(saved_data)
  Wait.time(function()
    if self then
      self.createButton({
        label="Reload Teams",
        click_function="click_reload_teams",
        function_owner=self,
        position={0,0.5,0}, rotation={0,0,0},
        height=400, width=1200,
        font_size=300, color={0,0.5,1}, font_color={1,1,1}
      })
      broadcastToAll("Bag of Boxes loaded. Click 'Reload Teams' to fetch latest team boxes.", {0, 0.7, 1})
    end
  end, 0.5)
end

function click_reload_teams()
  broadcastToAll("Fetching team list from GitHub...", {1, 1, 0})
  
  -- Fetch the JSON from GitHub
  WebRequest.get(DATACARDS_URLS_JSON_URL, function(webReturn)
    if webReturn.is_error then
      broadcastToAll("Error fetching team list: " .. webReturn.error, {1, 0, 0})
      return
    end
    
    -- Parse JSON
    local success, urlsData = pcall(function() return JSON.decode(webReturn.text) end)
    if not success then
      broadcastToAll("Error parsing JSON: " .. tostring(urlsData), {1, 0, 0})
      return
    end
    
    -- Filter for tts_card_box_object entries with deduplication
    local teamBoxes = {}
    local seenTeams = {}
    for _, entry in ipairs(urlsData) do
      if entry.type == "tts_card_box_object" then
        -- Skip duplicates based on team slug
        if not seenTeams[entry.team] then
          seenTeams[entry.team] = true
          table.insert(teamBoxes, {
            name = entry.name,
            url = entry.url,
            team = entry.team
          })
        else
          broadcastToAll("Skipping duplicate: " .. entry.team, {1, 0.5, 0})
        end
      end
    end
    
    broadcastToAll("Found " .. #teamBoxes .. " unique team boxes (from " .. #urlsData .. " total entries). Starting reload...", {0, 1, 0})
    
    -- Clear existing boxes
    local existingObjects = self.getObjects()
    broadcastToAll("Removing " .. #existingObjects .. " existing boxes...", {1, 1, 0})
    
    for _, obj in ipairs(existingObjects) do
      local taken = self.takeObject({guid = obj.guid})
      if taken then
        Wait.time(function()
          if taken then taken.destruct() end
        end, 0.1)
      end
    end
    
    -- Wait for bags to be empty, then spawn new boxes
    Wait.time(function()
      spawnTeamBoxes(teamBoxes, 1)
    end, 1.0)
  end)
end

function spawnTeamBoxes(teamBoxes, index)
  if index > #teamBoxes then
    broadcastToAll("Reload complete! Loaded " .. #teamBoxes .. " team boxes.", {0, 1, 0})
    return
  end
  
  local box = teamBoxes[index]
  broadcastToAll("Loading " .. index .. "/" .. #teamBoxes .. ": " .. box.name, {0, 0.7, 1})
  
  -- Add cache bust to URL
  local cacheBust = math.random(1, 999999)
  local urlWithCache = box.url .. "?v=" .. cacheBust
  
  -- Fetch the JSON for this box
  WebRequest.get(urlWithCache, function(webReturn)
    if webReturn.is_error then
      broadcastToAll("Failed to fetch " .. box.name .. ": " .. webReturn.error, {1, 0, 0})
      -- Continue with next box
      spawnTeamBoxes(teamBoxes, index + 1)
      return
    end
    
    -- Spawn the box from the fetched JSON
    spawnObjectJSON({
      json = webReturn.text,
      position = self.getPosition() + Vector(0, 5, 0),
      callback_function = function(spawnedObj)
        if spawnedObj then
          -- Put the spawned box into this bag
          Wait.time(function()
            self.putObject(spawnedObj)
            -- Process next box
            spawnTeamBoxes(teamBoxes, index + 1)
          end, 0.5)
        else
          broadcastToAll("Failed to spawn: " .. box.name, {1, 0, 0})
          -- Continue with next box even if this one failed
          spawnTeamBoxes(teamBoxes, index + 1)
        end
      end
    })
  end)
end

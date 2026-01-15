-- constants
local BUTTON_SETUP = {
  label="Setup",
  click_function="click_setup", function_owner=self,
  position={0,0.3,-2}, rotation={0,180,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_SETUP_2 = {
  label="Setup",
  click_function="click_setup",
  function_owner=self,
  position={-1,0.5,0}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_RECALL = {
  label="Recall",
  click_function="click_recall", function_owner=self,
  position={1,0,-1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={1,0,0}, font_color={1,1,1}
}
local BUTTON_PLACE = {
  label="Place",
  click_function="click_place",
  function_owner=self,
  position={1,0,1}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0.2,0.95,0}, font_color={0,0,0}
}
local BUTTON_CANCEL = {
  label="Cancel",
  click_function="click_cancel",
  function_owner=self,
  position={0,0.3,-2}, rotation={0,180,0},
  height=350, width=1100,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_SUBMIT = {
  label="Submit",
  click_function="click_submit", function_owner=self,
  position={0,0.3,-2.8}, rotation={0,180,0},
  height=350, width=1100,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}
local BUTTON_RESET = {
  label="Reset",
  click_function="click_reset",
  function_owner=self,
  position={-2,0.3,0}, rotation={0,270,0},
  height=350, width=800,
  font_size=250, color={0,0,0}, font_color={1,1,1}
}

-- functional utils
local function transmute(t, vfn, kfn)
    local out = {}
    local c = 1
    for k,v in pairs(t) do
        local value = vfn(v,c,t)
        local key = kfn != nil and kfn(v,c,t) or k
        if (value and key) then
            out[key] = value
        end
        c = c + 1
    end
    return out
end

local function duplicateTable(oldTable)
  local newTable = {}
  for k, v in pairs(oldTable) do
    newTable[k] = v
  end
  return newTable
end

local function round(num, dec)
  local mult = 10^(dec or 0)
  return math.floor(num * mult + 0.5) / mult
end

-- object utils
local function setOutline(list, enabled)
  local count = 0

  if (next(list) == nil) then
    return count
  end

  for guid in pairs(list) do
    count = count + 1
    local obj = getObjectFromGUID(guid)
    if (obj ~= nil and enabled == false) then obj.highlightOff() end
    if (obj ~= nil and enabled == true) then obj.highlightOn({1,1,1}) end
  end

  return count
end

local function readRotation()
  local r1, r2, r3 = self.getRotation():get()
  return round(r2)
end

local function changeButtons(variant)
  self.clearButtons()

  if(variant == 'before_setup') then
    self.createButton(BUTTON_SETUP)
  elseif (variant == 'in_setup') then
    self.createButton(BUTTON_CANCEL)
    self.createButton(BUTTON_SUBMIT)
    self.createButton(BUTTON_RESET)
  elseif (variant == 'done_setup') then
    self.createButton(BUTTON_PLACE)
    self.createButton(BUTTON_RECALL)
    self.createButton(BUTTON_SETUP_2)
  end
end

function compare_coords(p1, p2, rotation)
  local deltaPos = {}
  r = math.rad(rotation)

  z = ((-p2.x * math.sin(r) + p2.z * math.cos(r)))
  x = ((p2.x * math.cos(r) + p2.z * math.sin(r)))

  deltaPos.x = (p1.x+x)
  deltaPos.y = (p1.y+p2.y)
  deltaPos.z = (p1.z+z)

  return deltaPos
end


--state utils
local function readList()
  return transmute(
    getObjectsWithTag(self.getGMNotes()),
    function(obj)
      local selfPos = self.getPosition()
      local objPos = obj.getPosition()
      local deltaPos = {}
      deltaPos.x = (objPos.x-selfPos.x)
      deltaPos.y = (objPos.y-selfPos.y)
      deltaPos.z = (objPos.z-selfPos.z)
      local pos, rot = deltaPos, obj.getRotation()

      return {
        pos={x=round(pos.x,4), y=round(pos.y,4), z=round(pos.z,4)},
        rot={x=round(rot.x,4), y=round(rot.y,4), z=round(rot.z,4)},
        lock=obj.getLock()
      }
    end,
    function(obj)
      return obj.guid
    end
  )
end


function updateSave()
  local data_to_save = {["ml"]=memoryList, ["rr"]=relativeRotation}
  saved_data = JSON.encode(data_to_save)
  self.script_state = saved_data
end

function onload(saved_data)
  if saved_data ~= "" then
    local loaded_data = JSON.decode(saved_data)
    --Set up information off of loaded_data
    memoryList = loaded_data.ml
    relativeRotation = loaded_data.rr
  else
    --Set up information for if there is no saved saved data
    memoryList = {}

    relativeRotation = readRotation()
  end

  if next(memoryList) == nil then
    changeButtons('before_setup')
  else
    changeButtons('done_setup')
  end
end

-- handlers for buttons
function click_setup()
  local tagTarget = self.getGMNotes()

  if (tagTarget == nil or tagTarget == '') then
    broadcastToAll('please specify a tag to target in GM notes')
    return
  end

  memoryListBackup = duplicateTable(memoryList)
  memoryList = readList()

  if (next(memoryList) == nil) then
    broadcastToAll('The tag you specified yielded in 0 objects')
    return
  end

  setOutline(memoryList, true)

  relativeRotationBackup = relativeRotation
  relativeRotation = readRotation()

  changeButtons('in_setup')
end

function click_cancel()
  setOutline(memoryList, false)

  memoryList = memoryListBackup
  relativeRotation = relativeRotationBackup

  if next(memoryList) == nil then
    changeButtons('before_setup')
  else
    changeButtons('done_setup')
  end

  broadcastToAll("Selection Canceled", {1,1,1})
end

function click_submit()
  memoryList = readList()
  if (next(memoryList) == nil) then
    broadcastToAll("You cannot submit without any selections.", {0.75, 0.25, 0.25})
  else
    changeButtons('done_setup')

    local count = setOutline(memoryList, false)
    broadcastToAll(count.." Objects Saved", {1,1,1})

    updateSave()
  end
end

function click_reset()
  setOutline(memoryList, false)
  memoryList = {}

  relativeRotation = readRotation()

  changeButtons('before_setup')

  broadcastToAll("Tool Reset", {1,1,1})
  updateSave()
end

function click_place()

  local bagObjList = self.getObjects()
  local currentRotation = readRotation()

  local newMemoryList = {}
  local printed = false
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    local selfPos = self.getPosition()
    local rot = { x=entry.rot.x, y=entry.rot.y, z=entry.rot.z }
    local rotationAdjustment = currentRotation - relativeRotation

    rot.y = rot.y + rotationAdjustment
    if (rot.y > 360) then
      rot.y = rot.y - 360
    elseif (rot.y < 0) then
      rot.y = rot.y + 360
    end

    --If obj is out on the table, move it to the saved pos/rot
    if obj ~= nil then
      local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
      obj.setPosition(deltaPos)
      obj.setRotation(rot)
      obj.setLock(entry.lock)
      newMemoryList[obj.guid] = memoryList[obj.guid]
    else
      --If obj is inside of the bag
      for _, bagObj in ipairs(bagObjList) do

        if bagObj.guid == guid then

            local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
            local item = self.takeObject({
              guid=guid,
              position=deltaPos,
              rotation=rot,
              smooth=false
            })

            newItem = item.clone({
              position=deltaPos,
              rotation=rot,
              smooth=false
            })
            item.destruct()

            newItem.setLock(entry.lock)
            newItem.setPosition(deltaPos)
            newMemoryList[newItem.guid] = memoryList[guid]
          break
        end
      end
    end
  end

  memoryList = {}
  for k,v in pairs(newMemoryList) do
   memoryList[k] = v
  end
  broadcastToAll("Objects Placed", {1,1,1})
updateSave()
end

function click_recall()
  for guid, entry in pairs(memoryList) do
    local obj = getObjectFromGUID(guid)
    if obj ~= nil then
      self.putObject(obj)
    end
  end
  broadcastToAll("Objects Recalled", {1,1,1})
end
KTUI_MODELSCRIPT_VERSION = "12167bfd1d3f"

KTUI_MODELSCRIPT = [==[KT_MODELSCRIPT_VERSION = "12167bfd1d3f"

self.clearContextMenu()

-- KTUI EXTENDER + KTMT Spaghetty mod--

-- Original mods by Nyirsh, Feuerfritas, Ixidior and Mal20k--



  self.addContextMenuItem("Save place", function(pc) savePosition() end)

  self.addContextMenuItem("Load place", function(pc) loadPosition() end)



-- [KT] Movement context item removed (we load our own movement).
self.addContextMenuItem("Targeting lines", function(pc)  agregaCono() end)



--parte2

function agregaRuta()

--Actualizado KTMT

CUBO = nill

DataObjeto = 

{

    type = "Custom_Model",

    scale = {1,1,1},

    rotation = {0, 0, 0},

    position = {85, 2, 100}

}

DataModel =

{

    mesh = "https://raw.githubusercontent.com/Ixidior/KTMT/main/"..state.base.x.."MM.obj",

    diffuse = "https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/KTMT%20Diffuse.png",

    collider = "https://raw.githubusercontent.com/Ixidior/KTMT/main/collider4.obj",

    type = 0,

    material = 0,

    specular_intensity = 0,

	specular_sharpness = 7,

	freshnel_strength = 0.4

   

}

if CUBO == nill then



        CUBO = spawnObject(DataObjeto)

	--print(CUBO.getGUID())

        CUBO.setCustomObject(DataModel)

	CUBO.angular_drag = 0.1

	CUBO.bounciness = 0

	CUBO.dynamic_friction = 0.7

	CUBO.drag = 0.1

	CUBO.mass = 1

	CUBO.static_friction = 1



end

 WebRequest.get("https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/KTMT%20Movement.lua", function(req)

local script = req.text

CUBO.setLuaScript(script)

CUBO.setVar("GUIDModel",self.getGUID())

CUBO.setVar("GUIDNodPrev",self.getGUID())

end



)

end



function agregaCono()

CONO = nill

DataObjetoCono = 

{

    type = "Custom_Model",

    scale = {1,1,1},

    rotation = {0, 0, 0},

    position = {0, 2, 0}

}

DataModelCono =

{

    mesh = "https://raw.githubusercontent.com/Ixidior/KTMT/refs/heads/main/CONE.obj",

    diffuse = "https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/KTMT%20Diffuse.png",

    collider = "https://raw.githubusercontent.com/Ixidior/KTMT/refs/heads/main/CONE_COLLIDER.obj",

    type = 0,

    material = 0,

    specular_intensity = 0,

	specular_sharpness = 7,

	freshnel_strength = 0.4

   

}

if CONO == nill then



        CONO = spawnObject(DataObjetoCono)

	--print(CUBO.getGUID())

        CONO.setCustomObject(DataModelCono)

	CONO.angular_drag = 120

	CONO.bounciness = 0

	CONO.dynamic_friction = 1

	CONO.drag = 120

	CONO.mass = 10

	CONO.static_friction = 1

	CONO.use_gravity = false



end

 WebRequest.get("https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/KTMT%20Target%20Cone.lua", function(req)

local script = req.text

CONO.setLuaScript(script)

--CONO.setColorTint(Color.fromString(pc))

--print(self.getGUID())

CONO.setVar("GUIDModel",self.getGUID())

end



)

--self.setLock(true)

--self.interactable = false





end

function agregaConoR()



CONO = nill

DataObjetoCono = 

{

    type = "Custom_Model",

    scale = {1,1,1},

    rotation = {0, 0, 0},

    position = {self.getPosition().x+1, self.getPosition().y, self.getPosition().z}

}

DataModelCono =

{

    mesh = "https://raw.githubusercontent.com/Ixidior/KTMT/refs/heads/main/CONE.obj",

    diffuse = "https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/KTMT%20Diffuse.png",

    collider = "https://raw.githubusercontent.com/Ixidior/KTMT/refs/heads/main/CONE.obj",

    type = 0,

    material = 0,

    specular_intensity = 0,

	specular_sharpness = 7,

	freshnel_strength = 0.4

   

}

if CONO == nill then



        CONO = spawnObject(DataObjetoCono)

	--print(CUBO.getGUID())

        CONO.setCustomObject(DataModelCono)

	CONO.angular_drag = 120

	CONO.bounciness = 0

	CONO.dynamic_friction = 1

	CONO.drag = 120

	CONO.mass = 10

	CONO.static_friction = 1

	CONO.use_gravity = true



end

 WebRequest.get("https://raw.githubusercontent.com/Ixidior/KTMT/refs/heads/main/ScriptConoR", function(req)

local script = req.text

CONO.setLuaScript(script)

--CONO.setColorTint(Color.fromString(pc))

--print(self.getGUID())

CONO.setVar("GUIDModel",self.getGUID())

end



)

--self.setLock(true)

--self.interactable = false





end



-----------------------------------------------

-----------------------------------------------



state = {}



self.max_typed_number=99



ranges = {

  triangle={

    color=Color(0.10,0.10,0.09),

    range=1

  },

  circle={

    color=Color(1,1,1),

    range=2

  },

  square={

    color=Color(0,0.36,0.62),

    range=3

  },

  pentagon={

    color=Color(0.80,0.08,0.09),

    range=6

  }

}



triangle = "(1\")"

circle   = "(2\")"

square   = "(3\")"

pentagon = "(6\")"



function textColorXml( color, text )

  return string.format("<textcolor color=\"#%s\">%s</textcolor>", color, text)

end



function textColorMd( color, text )

  return string.format("[%s]%s[-]", color, text)

end



secrets = {

  "ktcnid-status-hiddenRole"

}



text_subs = {

  ["1&&"]   = textColorXml("000000", triangle),

  ["2&&"]   = textColorXml("ffffff", circle),

  ["3&&"]   = textColorXml("1E87FF", square),

  ["6&&"]   = textColorXml("DA1A18", pentagon),

  ["%(R%)"] = textColorXml("1E87FF", "R"),

  ["%(M%)"] = textColorXml("F4641D", "M")

}



md_subs = {

  ["1&&"]   = textColorMd("000000", triangle),

  ["2&&"]   = textColorMd("ffffff", circle),

  ["3&&"]   = textColorMd("1E87FF", square),

  ["6&&"]   = textColorMd("DA1A18", pentagon),

  ["%(R%)"] = textColorMd("1E87FF", "R"),

  ["%(M%)"] = textColorMd("F4641D", "M")

}



function secretVisibility()

  local p = getOwningPlayer()

  if p == nil then return "" end

  return table.concat( {"Jokers", p.color}, "|" )

end



function hideSecrets()

  local sv = secretVisibility()

  for i,v in ipairs(secrets) do

    self.UI.setAttribute(v, "visibility", sv)

  end

end



modelMeasureLineRadius = 0.05

base                   = {}

baseLineRadius         = 0.0125

baseLineHeight         = 0.2



rangeShown             = false

measureColor           = nil

measureRange           = 0



function onNumberTyped( pc, n )

  local handled = true

  rangeShown = n > 0

  measureColor = Color.fromString(pc)

  measureRange = n



  scaleFactor = 1/self.getScale().x



  if lastRange == measureRange then

    sphereRange = getCircleVectorPoints(measureRange - modelMeasureLineRadius + 0.05, 0.125, 1)[1].x * 2 / scaleFactor

    Physics.cast({

          origin       = self.getPosition(),

          direction    = {0,1,0},

          type         = 2,

          size         = {sphereRange,sphereRange,sphereRange},

          max_distance = 0,

          debug        = true,

    })

    handled = false -- allow other handlers to trigger (eg: state change)

  end

  lastRange = measureRange

  refreshVectors()

  Player[pc].broadcast(string.format("%d\"", measureRange))

  return handled

end



function saveState()

  local old_state = self.script_state

  -- why are we missing attachments?

  if state.attachments == nil then

    state.attachments = {}

  end

  self.script_state = JSON.encode(state)

  if old_state != self.script_state then

    local event = {

      guid = self.getGUID(),

      old_state = old_state,

      cur_state = self.script_state

    }

    local gamelogGuid = "bafa93"

    local _kt_gl = getObjectFromGUID(gamelogGuid)
    if _kt_gl then _kt_gl.call("gameLogAppendOperativeChangedState", event) end

  end

end



function loadState()

  state = JSON.decode(self.script_state)

end



function savePosition(p, r)

  local savePos = {

    position=p or self.getPosition(),

    rotation=r or self.getRotation()

  }

  state.savePos = savePos

  saveState()

  self.highlightOn(Color(0.19, 0.63, 0.87), 0.5)

end



function loadPosition()

  local sp = state.savePos

  local event = {

    id = self.getGUID(),

    operative = self.getName(),

    coords= sp.position,

    old_coords = self.getPosition()

  }

  if sp then

    self.setPositionSmooth(sp.position, false, true)

    self.setRotationSmooth(sp.rotation, false, true)

    self.highlightOn(Color(0.87, 0.43, 0.19), 0.5)

  end

  local gamelog = getObjectFromGUID("bafa93")

  if gamelog then

    gamelog.call("gameLogAppendOperativeMovedEvent", event)

  end

end



-- Nyirsh: a bit redundant with the RefreshUI, maybe we can put these two together

function refreshWounds()



  local w = state.wounds

  local m = state.stats.Wounds



  local uiwstring = function()

    if w == 0 then

      return textColorXml("DA1A18", "DEAD")

    end

    return string.format("%d/%d", w, m)

  end



  local namewstring = function()

    if w == 0 then

      return "{[DA1A18]DEAD[-]}"

    elseif w < m/2 then

      return string.format("{[9A1111]*[-]%d/%d[9A1111]*[-]}", w, m)

    end

    return string.format("{%d/%d}", w, m)

  end





  self.UI.setValue("ktcnid-status-wounds", uiwstring())

  local nname = self.getName()



  if string.find(nname, "%b{}") == nil then

    nname = "{} "..nname

  else

    nname = string.sub(nname, string.find(nname, "%b{}"), 100)

  end



  local norder = "[FF5500]"

  if state.ready == false then

    norder = "[999999]"

  end



  if state.order == "Conceal" then

    norder = norder.."C"

  else

    norder = norder.."E"

  end

  norder = norder.."[-] "



  self.setName(string.gsub(nname, "%b{}", norder..namewstring()))

end



function callback_attachment(player, value, id)

  local attachment = id:gsub("ktcnid[-]status[-]", "")

  local mustRefresh = false

  if state.attachments[attachment].active == false or state.attachments[attachment].removable == false then return end

  if state.attachments[attachment].stackable then

    local stackModifier = -1

    if value == "-1" then stackModifier = 1 end

    state.attachments[attachment].stack = state.attachments[attachment].stack + stackModifier

    if state.attachments[attachment].stack <= 0 then

      state.attachments[attachment].stack = 0

      state.attachments[attachment].active = false

    end

    mustRefresh = true

  else

    if value == "-2" then

      state.attachments[attachment].active = false

      mustRefresh = true

    end

  end



  if mustRefresh then

    saveState()

    refreshUI()

  end

end



function callback_secret(player, value, id)

  local attachment = id:gsub("ktcnid[-]status[-]", "")

  if value == "-1" then

    state.attachments[attachment].active = not state.attachments[attachment].active

  end

  saveState()

  refreshUI()

end



function callback_orders(player, value, id)

  if value == '-1' then

    if state.ready == nil or state.ready then

      state.ready = false

    else

      state.ready = true

    end

    if state.order == "Guard" or state.order == "GuardConceal" then

      state.order = "Engage"

      state.ready = false

    end

  elseif

    state.order == "Guard" or state.order == "GuardConceal" then

      state.order = "Engage"

      state.ready = false

  else

    if state.order == "Engage" then

      state.order = "Conceal"

    else

      state.order = "Engage"

    end

  end

  refreshUI()

  refreshWounds()

  saveState()

end



-- HP Bar ===========================

local function getWoundPanelWidth()

  local wounds = state.stats and state.stats.Wounds or 0

  if wounds <= 7 then

    return 60

  elseif wounds <= 10 then

    return 80

  elseif wounds <= 14 then

    return 100

  elseif wounds <= 18 then

    return 120

  else

    return 140

  end

end



function buildHPBar()

  local maxWounds = state.stats.Wounds or 0

  local currentWounds = state.wounds or 0

  local panelWidth = getWoundPanelWidth()

  local rectHeight = 23

  local filledWidth = 0



  if maxWounds > 0 then

    filledWidth = math.floor(panelWidth * currentWounds / maxWounds)

  end



  local barColor = "#098e00"

  if currentWounds < (maxWounds / 2) then

    barColor = "#FF0000"

  elseif currentWounds < maxWounds then

    barColor = "#e29300"

  else

    barColor = "#098e00"

  end



  return '<Panel width="'..panelWidth..'" height="'..rectHeight..'" color="#000000" outline="#FF5500" outlineSize="2 2" rectAlignment="LowerCenter" raycastTarget="false">'..

           '<Panel width="'..filledWidth..'" height="'..rectHeight..'" color="'..barColor..'" rectAlignment="MiddleLeft" raycastTarget="false" />'..

         '</Panel>'

end



-- ====================================



function refreshUI()

  local sc = self.getScale()

  local scaleFactorX = 1/sc.x

  local scaleFactorY = 1/sc.y

  local scaleFactorZ = 1/sc.z



  local circOffset = function(d, a)

    local ra = math.rad(a)

    return string.format("%d %d", math.cos(ra)*d, math.sin(ra)*d)

  end



  local off_injured = -35

  local off_order = 65

  if state.display_arrows then

    off_injured = -75

    off_order = 95

  end



  local p = getOwningPlayer()

  local wound_color = (p ~= nil and p.color ~= "Red") and "blue" or "red"



  local position = getUIPosition()



  local hpBarXML = '<Panel offsetXY="'..circOffset(0, 90)..'" rectAlignment="UpperCenter">'..buildHPBar()..'</Panel>'



  local woundPanelWidth = getWoundPanelWidth()



  local xmlTable = [[<Defaults>

    <Image class="statusDisplay" hideAnimation="Shrink" showAnimation="Grow" preserveAspect="true" />

   </Defaults>

   <Panel position="]]..position..[[" width="100" height="100" rotation="0 0 ]]..(state.uiAngle or 0)..[[" scale="]]..scaleFactorX..[[ ]]..scaleFactorY..[[ ]]..scaleFactorZ..[[">



    <HorizontalLayout spacing="3" width="@totalSecret" height="20" offsetXY="-30 -10">

      --@EquipmentPlaceholder

      --@SecretsPlaceholder

    </HorizontalLayout>



    ]]..hpBarXML..[[



    <Panel color="#80808000" outline="#FF5500" outlineSize="2 2" width="]]..woundPanelWidth..[[" height="25" offsetXY="]]..circOffset(40, 270)..[[">

      <Text id="ktcnid-status-wounds" text="]]..string.format("%d/%d", state.wounds or 0, state.stats.Wounds or 0)..[[" resizeTextForBestFit="true" color="#ffffff" rectAlignment="UpperCenter" onClick="change_wounds" />

      <Image id="ktcnid-status-injured" image="Wound_]]..wound_color..[[" width="30" height="30" rectAlignment="MiddleLeft" offsetXY="]]..off_injured..[[ 0" active="]]..tostring(isInjured())..[[" />

      <Image id="ktcnid-status-order" image="]]..getCurrentOrder()..[[" rectAlignment="MiddleRight" width="55" height="55" offsetXY="]]..off_order..[[ 0" active="true" onClick="callback_orders" />

    </Panel>



    <HorizontalLayout spacing="3" width="@totalAtt" height="30" offsetXY="]]..circOffset(80, 270)..[[">

      --@AttachmentPlaceholder

    </HorizontalLayout>

  </Panel>]]





  local hasRoles = next(state.roles) ~= nil

  local hiddenRoles = next(state.hiddenRoles) ~= nil

  local holding = state.holding

  local items = next(state.items) ~= nil



  xmlTable = xmlTable:gsub("@items", tostring(items))



  local totalAtt = 0

  local totalStack = 0

  local totalSecrets = 0



  local secretxmlAttachmentFormatted = "--@SecretsPlaceholder"



  if state.attachments == nil then

    -- whyy

    state.attachments = {}

  end

  for _,i in pairs(state.attachments) do

    if i.equipment == true and i.active == true then

      totalSecrets = totalSecrets + 1

      local xmlAttachmentFormatted = [[<Image id="ktcnid-status-]]..i.name..[[" image="]]..i.name..[[" width="30" height="30" preserveAspect="true"]]

      xmlAttachmentFormatted = xmlAttachmentFormatted..[[ active="true" onclick="callback_attachment" /> --@EquipmentPlaceholder]]

      xmlTable = xmlTable:gsub("--@EquipmentPlaceholder", xmlAttachmentFormatted)

    elseif i.secret == false then

      if i.active then

        totalAtt = totalAtt + 1

        local xmlAttachmentFormatted = [[<Image id="ktcnid-status-]]..i.name..[[" image="]]..i.name..[[" width="30" height="30" preserveAspect="true" ]]

        if i.removable then xmlAttachmentFormatted = xmlAttachmentFormatted..[[ onclick="callback_attachment" ]] end

        xmlAttachmentFormatted = xmlAttachmentFormatted..[[ active="true" /> --@AttachmentPlaceholder]]

        if i.stackable and (i.stack or 0) > 0 then

          totalStack = totalStack + 1

          xmlAttachmentFormatted = [[<Panel width="30" height="30"><Text id="ktcnid-status-stack-]]..i.name..[[" text="]]..i.stack..[[x" width="20" rectAlignment="Middle" color="#ffffff" /></Panel> ]]..xmlAttachmentFormatted

        end

        xmlTable = xmlTable:gsub("--@AttachmentPlaceholder", xmlAttachmentFormatted)

      end

    else

      totalSecrets = totalSecrets + 1

      local xmlAttachmentFormatted = [[<Image id="ktcnid-status-]]..i.name..[[" image="]]..i.name..[[" width="30" height="30" preserveAspect="true"]]

      if i.active then

        xmlAttachmentFormatted = xmlAttachmentFormatted..[[ visibility="]]..tostring(sv)..[[" color="#333333DD" ]]

      end

      xmlAttachmentFormatted = xmlAttachmentFormatted..[[ active="true" onclick="callback_secret" /> --@SecretsPlaceholder]]



      if i.active then

        secretxmlAttachmentFormatted = secretxmlAttachmentFormatted:gsub("--@SecretsPlaceholder", xmlAttachmentFormatted)

      else

        xmlTable = xmlTable:gsub("--@SecretsPlaceholder", xmlAttachmentFormatted)

      end

    end

  end

  --xmlTable = xmlTable:gsub("@items", "true")



  xmlTable = xmlTable:gsub("@totalAtt", tostring((totalAtt * 30) + (totalStack * 25)))

  xmlTable = xmlTable:gsub("@totalSecret", tostring((totalSecrets * 30)))

  xmlTable = xmlTable:gsub("--@SecretsPlaceholder", secretxmlAttachmentFormatted)





  self.UI.setXml(xmlTable)

  if state.wounds == 0 then

    Wait.frames(function() refreshWounds() end, 1)

  end

end



function createUI()

  local baseBundle = {

    {name="Engage_ready", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Engage%20Ready.png?v=2]=]},

    {name="Engage_activated", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Engage%20Expended.png?v=2]=]},

    {name="Conceal_ready", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Conceal%20Ready.png?v=2]=]},

    {name="Conceal_activated", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Conceal%20Expended.png?v=3]=]},

    {name="Guard_ready", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Guard.png]=]},

    {name="Guard_activated", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Guard.png]=]},

    {name="GuardConceal_ready", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Guard%20Conceal.png]=]},

    {name="GuardConceal_activated", url=[=[https://raw.githubusercontent.com/xSpaghettyx/KT24-Table-The-Killzone-Mod/refs/heads/main/Guard%20Conceal.png]=]},

    {name="Wound_blue",   url=[=[https://steamusercontent-a.akamaihd.net/ugc/1857171492582455772/CFB7B4D001501AC54B4D0CC7FEE35AF679B73D34/]=]},

	  {name="Wound_red",   url=[=[https://steamusercontent-a.akamaihd.net/ugc/1857171826950614938/C515FF37C3D1D269533C1B5FDA675895F792BC15/]=]},

  }



  for _,i in pairs(state.attachments) do

    table.insert(baseBundle, {name=i.name, url=i.url})

  end

  self.UI.setCustomAssets(baseBundle)

end



function isInjured()

  return state.stats.Wounds and state.wounds < state.stats.Wounds / 2 or false

end



local notifyTimer = nil

local pendingMessage = nil



-- notification logic update ==============================

function notify(pc, message)

  if type(pc) == "userdata" then

    pc = pc.color

  end



  pendingMessage = message



  if notifyTimer then

    Timer.destroy(notifyTimer)

    notifyTimer = nil

  end



  notifyTimer = "notifyTimer_" .. math.random(1000000)

  Timer.create({

    identifier = notifyTimer,

    function_name = "notifyBroadcast",

    delay = 0.7

  })

end

-- ======================================================



function notifyBroadcast()

  if pendingMessage then

    broadcastToAll(pendingMessage)

    pendingMessage = nil

  end

  notifyTimer = nil

end



function change_wounds(player, value, id)

  if value == "-1" then

    damage()

  elseif value == "-2" then

    heal()

  end

end



function damage(pc)

  local si = isInjured()

  state.wounds = math.max(0, (state.wounds or 0) - 1)

  if not si and isInjured() then

    self.UI.show("ktcnid-status-injured")

  end

  saveState()

  refreshWounds()

  refreshUI()

  notify(pc, string.format("%s took damage", self.getName()))

end



function heal(pc)

  local si = isInjured()

  state.wounds = math.min((state.stats.Wounds or 0), (state.wounds or 0) + 1)

  if si and not isInjured() then

    self.UI.hide("ktcnid-status-injured")

  end

  saveState()

  refreshWounds()

  refreshUI()

  notify(pc, string.format("%s recovered", self.getName()))

end



function kill(pc)

  state.wounds = 0

  saveState()

  refreshWounds()

  notify(pc, string.format("%s KO", self.getName()))

end



function updateStats(pc)

  if getOwningPlayer().color ~= pc then

      notify(pc, "Only the model's owner can update stats")

      return

  end

  notify(pc, "Updating stats from values in description")

  local statsub = {}

  local prevW = state.stats.Wounds or 0

  local wounds = state.wounds or 0

  local desc = self.getDescription() or ""

  local innerUpdate = function(stat)

      local statNames = {

          ["WOUNDS"] = "Wounds",

          ["APL"] = "APL",

          ["MOVE"] = "Move",

          ["SAVE"] = "Save",

      }

      local innerStat = statNames[stat]

      local sstring = "%[84E680%]" .. stat .. "%[%-%]%s*%[ffffff%]%s*(%d+).*%[%-%]"

      for match in string.gmatch(desc, "%b[]") do

          local s = match:match(sstring)

          if s then

              local ss = state.stats[innerStat]

              table.insert(statsub, string.format("%s = %s", stat, s))

              if ss and ss == tonumber(s) then

                  return false

              end

              state.stats[innerStat] = tonumber(s)



              -- notify(pc, string.format("%s set to %s", stat, s))

              return true

          end

      end

      table.insert(statsub, string.format("%s = [ff0000]X[-]", stat))

      return false

  end

  innerUpdate("APL")

  innerUpdate("MOVE")

  innerUpdate("SAVE")

  if innerUpdate("WOUNDS") then

      if wounds == prevW then

          state.wounds = state.stats.Wounds or 0

      else

          state.wounds = min(state.stats.Wounds or 0)

      end

      refreshWounds()

  end

  saveState()

  notify(pc, table.concat(statsub, ", "))

end



function onLoad(ls)

  loadState()



  if not state.stats then

    state.stats = {}

  end



  if state.stats.Wounds == nil and state.stats.W then

      state.stats.Wounds = tonumber(state.stats.W) or 0

  end

  if state.stats.Move == nil and state.stats.M then

      state.stats.Move = tonumber(state.stats.M) or 0

  end

  if state.stats.Save == nil and state.stats.SV then

      state.stats.Save = tonumber(state.stats.SV) or 0

  end



  if state.wounds == nil then

      state.wounds = state.stats.Wounds or 0

  elseif state.wounds > (state.stats.Wounds or 0) then

      state.wounds = state.stats.Wounds or 0

  end



  state.display_arrows = false

  if state.attachments == nil then

    state.attachments = {}

  end



  self.addContextMenuItem("Update stats", updateStats)



  for i, w in ipairs(state.info.weapons) do

    local weaponName = string.sub(w.name,1,21):gsub("%(R%)", "[1E87FF]R[-]"):gsub("%(M%)", "[F4641D]M[-]")

  	if string.len(w.name) > 21 then

  		weaponName = weaponName.."..."

  	end

  end



if state.uiPositionIndex == nil then

        state.uiPositionIndex = 1

    end



    self.addContextMenuItem("Change UI position", function(pc)

        state.uiPositionIndex = state.uiPositionIndex + 1

        if state.uiPositionIndex > 5 then

            state.uiPositionIndex = 1

        end

        refreshUI()

    end, true)





  local taglist = {state.modelid, "Operative"}

  for _,category in pairs(state.info.categories) do

    table.insert(taglist, category)

  end

  self.setTags(taglist)

  self.addTag("KTUIMini")

  createUI()

  refreshUI()

  refreshVectors(true)

  Wait.frames(function() refreshWounds() end, 1)

end



function callback_Attack(i)

    local weaponName = state.info.weapons[i].name:gsub("%(R%)", "[1E87FF]R[-]"):gsub("%(M%)", "[F4641D]M[-]")

    local weaponAttacks = state.info.weapons[i].stats["ATK"]

    local weaponLimit = state.info.weapons[i].stats["HIT"]



	if isInjured() == true then

		weaponLimit = weaponLimit + 1

		print("Attacking with "..weaponName.." "..weaponAttacks.."D6 @ [FF0000]"..weaponLimit.."+[-]")

	else

		print("Attacking with "..weaponName.." "..weaponAttacks.."D6 @ "..weaponLimit)

	end

    local op = getOwningPlayer()

    local roller = nil

    if op == nil then

      return

    end



    for _, obj in ipairs(getAllObjects()) do

      if obj.hasTag("KTUIDiceRoller") then

        roller = obj

      end

    end



    if roller == nil then return end



    Wait.frames(function()

      Player[op.color].clearSelectedObjects()

      roller.call("askSpawn", { player = op, number = weaponAttacks, auto = 1})

    end, 5)

end



function setGuard()

  state.order = "Guard"

  state.ready = true

  refreshUI()

end



function setGuardConceal()

  state.order = "GuardConceal"

  state.ready = true

  refreshUI()

end



function setEngage()

  state.order = "Engage"

  state.ready = true

  refreshUI()

end



function setConceal()

  state.order = "Conceal"

  state.ready = true

  refreshUI()

end



function getCurrentOrder()

  local orderName = state.order or "Engage"

  if state.ready == nil or state.ready then

    return orderName.."_ready"

  else

    return orderName.."_activated"

  end

end



function onPickUp(pc)

  if rangeShown then

    refreshVectors(true)

  end

end



function tryRandomize(playerColor)

    local manager = getObjectFromGUID("efa3fe")

    if not manager then

        return false

    end

    manager.call("onOperativeRandomize", { self, playerColor })



    return false

end



function getOwningPlayer()

  for _, player in ipairs(Player.getPlayers()) do

    if player.steam_id == state.owner then

      return player

    end

  end

  return nil

end



function setOwningPlayer(newOwner)

	state.owner = newOwner

end



function onPlayerChangeColor(color)

  if color ~= "Grey" then

    local p = Player[color]

    if p.steam_id == state.owner then

      refreshVectors()

      hideSecrets()

    end

  end

end



function refreshVectors(norotate)

  local op = getOwningPlayer()

  local circ = {}

  local scaleFactor = 1/self.getScale().x



  local rotation = self.getRotation()



  local newLines = {

    {

      points = getCircleVectorPoints(0 - baseLineRadius, baseLineHeight),

      color = op and Color.fromString(op.color) or {0.5, 0.5, 0.5},

      thickness = baseLineRadius*1*scaleFactor

    }

  }



  if rangeShown then

    if measureRange > 0 then

      table.insert(newLines,{

        points=getCircleVectorPoints(measureRange - modelMeasureLineRadius + 0.05, 0.125),

        color = measureColor,

        thickness = modelMeasureLineRadius*1*scaleFactor,

        rotation = (norotate and {0, 0, 0} or {-rotation.x, 0, -rotation.z})

      })

      end

    end



  self.setVectorLines(newLines)

end



function getCircleVectorPoints(radius, height, segments)

    local bounds = self.getBoundsNormalized()

    local result = {}

    local scaleFactorX = 1/self.getScale().x

    local scaleFactorY = 1/self.getScale().y

    local scaleFactorZ = 1/self.getScale().z

    local steps = segments or 64

    local degrees,sin,cos,toRads = 360/steps, math.sin, math.cos, math.rad

    local modelBase = state.base



    local mtoi = 0.0393701

    local baseX = modelBase.x * 0.5 * mtoi

    local baseZ = modelBase.z * 0.5 * mtoi



    for i = 0,steps do

        table.insert(result,{

            x = cos(toRads(degrees*i))*((radius+baseX)*scaleFactorX),

            z = sin(toRads(degrees*i))*((radius+baseZ)*scaleFactorZ),

            y = height*scaleFactorY

        })

    end



    return result

end



function doAutoSize()

  local nx = state.base.x

  local nz = state.base.z

  local bounds = self.getBoundsNormalized()

  if bounds.size.x == 0 or bounds.size.y == 0 then

      local r = self.getRotation()

      self.setRotation(Vector(0,0,0))

      bounds = self.getBounds()

      self.setRotation(r)

  end

  local scale = self.getScale()

  local xi = nx / 25.4

  local zi = nz / 25.4

  local xs = (xi / bounds.size.x) * scale.x

  local zs = (zi / bounds.size.z) * scale.z



  self.setScale(Vector(xs, (xs + zs) / 2, zs))

  refreshVectors()

end



function setBaseSize( x, z )

  state.base = {x=x, z=z}

  -- state.uiHeight=((x + z)/25)

  saveState()

  refreshVectors()

  refreshUI()

end



function addRole( role, hidden )

  local rg = hidden and state.hiddenRoles or state.roles

  local empty = next(rg) == nil

  table.insert(rg, role)

  if empty then

    self.UI.show(hidden and "ktcnid-status-hiddenRole" or "ktcnid-status-role")

  end

  saveState()

end



function removeRole( role )

  local rri = function( rg, id )

    local nr = {}

    for i,v in ipairs(rg) do

      if v ~= role then table.insert(nr, v) end

    end

    rg = nr

    if next(rg) == nil then

      self.UI.hide(id)

    end

  end

  rri(state.roles, "ktcnid-status-role")

  rri(state.hiddenRoles, "ktcnid-status-hiddenRole")

end



function revealRole( role )

  removeRole(role)

  addRole(role, false)

end



isColliding = false

function onCollisionEnter(a)

  if isColliding == true then

    return

  end



  if a.collision_object.getLock() == true then

    return

  end



  isColliding = true



  local mustRefresh = false

  if a.collision_object.hasTag("KTUITokenOrder") then

    local newState = a.collision_object.getDescription()

    a.collision_object.destruct()

    if newState:startswith("Engage") then state.order = "Engage" else state.order = "Conceal" end

    if newState:endswith("ready") then state.ready = true else state.ready = false end

    mustRefresh = true

  elseif a.collision_object.hasTag("KTUITokenGuard") then

    a.collision_object.destruct()

    state.ready = true

    state.order = "Guard"

    mustRefresh = true

  elseif a.collision_object.hasTag("KTUITokenGuardConceal") then

    a.collision_object.destruct()

    state.ready = true

    state.order = "GuardConceal"

    mustRefresh = true

  elseif a.collision_object.hasTag("KTUITokenSimple") or a.collision_object.hasTag("KTUITokenEquipment") or a.collision_object.hasTag("KTUIStackable") then

    local newState = a.collision_object.getDescription()

    local imageUrl = a.collision_object.getCustomObject().image

    local stackable = a.collision_object.getCustomObject().stackable or a.collision_object.hasTag("KTUIStackable")

    local equipment = a.collision_object.hasTag("KTUITokenEquipment")

    local removable = true

    a.collision_object.destruct()



    if equipment == true then

      stackable = false

      removable = false

    end



    -- If the token is new to the miniature, it adds it to the list of tokens

    if state.attachments[newState] == nil then

      state.attachments[newState] = { name = newState, url = imageUrl, removable = removable, stackable = stackable, secret = false, equipment = equipment, active = true, stack = 1 }

      saveState()

      createUI()

      refreshUI()

    else

      if state.attachments[newState].url ~= imageUrl then

        state.attachments[newState].url = imageUrl

        saveState()

        createUI()

        refreshUI()

      end



      if state.attachments[newState].active == false then

        state.attachments[newState].active = true

        state.attachments[newState].stack = 1

      else

        state.attachments[newState].stack = state.attachments[newState].stack + 1

      end

    end

    mustRefresh = true

  elseif a.collision_object.hasTag("KTUITokenAdvanced") then

    -- The idea is to have the token script itself giving more advanced information on its behaviour

    local newStateClass = a.collision_object.call('KTUI_GetTokenFace')

    a.collision_object.destruct()

    local newState = newStateClass.name

    local imageUrl = newStateClass.url

    local removable = newStateClass.removable

    local stackable = newStateClass.stackable

    local secret = newStateClass.secret

    local equipment = newStateClass.equipment



    if secret == true then

      removable = false

      stackable = false

      equipment = false

    end

    if equipment == true then

      stackable = false

    end



    -- If the token is new to the miniature, it adds it to the list of tokens

    if state.attachments[newState] == nil then

      state.attachments[newState] = { name = newState, url = imageUrl, removable = removable, stackable = stackable, secret = secret, equipment = equipment, active = true, stack = 0 }

      saveState()

      createUI()

      refreshUI()

      mustRefresh = true

    else

      if state.attachments[newState].url ~= imageUrl then

        state.attachments[newState].url = imageUrl

        saveState()

        createUI()

        refreshUI()

        mustRefresh = true

      end



      if state.attachments[newState].active == false then

        state.attachments[newState].active = true

      end

    end

    mustRefresh = true

  end



  if mustRefresh then

    saveState()

    refreshUI()

    Wait.frames(function() isColliding = false self.reload() end, 30)

  end

  Wait.frames(function() isColliding = false end, 40)

end





function KTUI_ReadyOperative()

  if state.order == "Guard" or state.order == "GuardConceal" then

      state.order = "Engage"

      state.ready = true

      refreshUI()

  else 

      state.ready = true

      refreshUI()

  end

end



function KTUI_CleanOperative()

  state.attachments = {}

  refreshUI()

end





function comCheckOwner(t)

  return t[1] == state.owner

end



function comBaseSize()

  return state.base

end



function comSetBase(t)

  setBaseSize(t.x, t.z)

end



function comAutoSize()

  doAutoSize()

  refreshUI()

end



function comSavePosition( t )

  savePosition(t.position, t.rotation)

end



function comLoadPosition()

  loadPosition()

end



function comAddRole( t )

  addRole(t.role, t.hidden)

end



function comRemoveRole( t )

  removeRole(t.role)

end



function comRevealRole( t )

  revealRole(t.role)

end



function comSetUIAngle( t )

  state.uiAngle = t.uiAngle

  saveState()

  refreshUI()

end



string.startswith = function(self, str)

    return self:find('^' .. str) ~= nil

end

string.endswith = function(self, str)

    return self:find(str .. "$") ~= nil

end



function getUIPosition()

    local uiHeight = state.uiHeight or 1

    local zScale = scaleFactorZ or 1



    if state.uiPositionIndex == 1 then

        return "0 30 -" .. tostring(uiHeight * 100 * zScale)

    elseif state.uiPositionIndex == 2 then

        return "0 30 -" .. tostring(uiHeight * 120 * zScale)

    elseif state.uiPositionIndex == 3 then

        return "0 30 -" .. tostring(uiHeight * 140 * zScale)

    elseif state.uiPositionIndex == 4 then

        local yScale = scaleFactorY or 1

        return "0 -" .. tostring(60 * yScale) .. " -" .. tostring(20 * zScale)

    elseif state.uiPositionIndex == 5 then

        return "0 30 -" .. tostring(uiHeight * 80 * zScale)

    end

end

-- KT model-side extension (appended AFTER the healed KTUI extender script).
-- This is OUR code that rides on top of the real extender model script, composed
-- into the single KTUI_MODELSCRIPT our cards stamp onto a model.
--
-- Append-safety relies on the composer healing getWoundPanelWidth first.
-- Slot for future model-side hooks (move/sprint/callout). When adding code, chain
-- onLoad: `local prev = onLoad; function onLoad(...) if prev then pcall(prev, ...) end ... end`.

-- START KT_EXTENSION_V1 --
local extenderGetUIPosition = getUIPosition

function getUIPosition()
	local position = extenderGetUIPosition()
	if not state.kt_node_ui or not position then return position end
	local horizontal, vertical, depth = position:match("^(%S+)%s+(%S+)%s+(%S+)$")
	horizontal, vertical = tonumber(horizontal), tonumber(vertical)
	local scale = self.getScale()
	local angle = math.rad(state.uiAngle or 0)
	local worldHorizontal = horizontal * scale.x
	local worldVertical = vertical * scale.z
	return string.format("%.6f %.6f %s",
		(worldHorizontal * math.cos(angle) - worldVertical * math.sin(angle)) / scale.x,
		(worldHorizontal * math.sin(angle) + worldVertical * math.cos(angle)) / scale.z,
		depth)
end
-- END KT_EXTENSION_V1 --
]==]

MOVE_TOOL_CODE = [=[--[[ ============================================================================
  MOVE TOOL  (Proof of Concept, v1)
  A general Kill Team "Normal Move" helper for any operative.

  What a move is
  --------------
  Unlike the Exodite sprint (locked facing + a single pivot), a normal move is a
  FREE PATH: you travel up to your Move stat in as many straight legs as you
  like, changing direction at each leg. Each leg's distance rounds UP to the
  whole inch when spent (so a 1.5" leg costs 2"). Movement is measured in full
  3D, so climbing or dropping onto terrain automatically costs distance.

  Controls
  --------
  While a move is active, for the driving player:
    1 = -1" to the max move   (injured, difficult terrain, etc.)
    2 = +1" to the max move   (charge, terrain bonus, etc.)
    9 = finish (commits the current leg, applies the move)
    0 = cancel the whole move
  Mouse (via an invisible click catcher pinned to the model):
    LEFT-click  = commit the current leg and start the next one
    RIGHT-click = undo the last leg (or cancel from the first leg)
  You aim with your pointer the whole time; the ghost follows the cursor,
  clamped to the remaining budget. Hovering the ghost over a building places it
  on top (the pointer already returns the surface under the cursor), and the
  climb is charged automatically as part of the 3D leg distance. Use 1/2 to
  hand-apply any extra rule-based cost on top.

  Preview
  -------
  A grey circle shows the remaining reach from the current point. Committed legs
  are drawn dim; the active leg is green; a cyan ghost of the base (with a front
  marker) shows where the model lands.

  Injection-safe loading
  -----------------------
  Can be APPENDED to a model that already has its own script:
    * onLoad / onPickUp / onScriptingButtonDown / onNumberTyped are CHAINED.
    * It never WRITES self.script_state (only reads it to size the base ghost).
    * The click catcher is a transparent button pinned to the model, sized to the
      current reach (resized live as the 1/2 keys change it) and removed by its
      own click_function, so it never calls clearButtons().
    * Globals it adds are uniquely named (setupMoveTool, moveOnPickUp,
      moveCatcherClick, moveScriptingButton + chained handlers).

  Assumes 1 TTS unit = 1 inch. Change UNITS_PER_INCH if your table scale differs.
============================================================================ ]]

-- ------------------------------------------------------------------ tuning ---
local MOVE_DEFAULT   = 6        -- fallback Move stat when none can be read (inches)
local DASH_INCHES    = 3        -- Dash action always starts from this budget (inches)
local UNITS_PER_INCH = 1        -- world units per inch (KT-UI table = 1)

-- Click-catcher: a transparent button pinned to the model, covering the CURRENT
-- leg's REMAINING reach + a margin (a disc centred on curPos), so hovering it
-- counts as hovering the model (the number ROW works with no key binding) and it
-- only locks a small area, not the table. As budget is spent (or the 1/2 keys
-- change it) the catcher re-centres and shrinks (resizeCatcher) to what's left.
local CATCHER_MARGIN_IN    = 1           -- inches of catch area past the reach
-- button-units per inch. TUNING KNOB: raise = bigger catcher, lower = smaller.
-- (14000/9 rendered ~2-3x too wide -- 40" for an 8" move; ~450 targets it.)
local CATCHER_UNITS_PER_IN = 450

-- Default base footprint (mm); used only when a model exposes no base metadata.
local DEF_BASE_MM_LONG = 32
local DEF_BASE_MM_WIDE = 32
local BASE_MM_LONG   = DEF_BASE_MM_LONG
local BASE_MM_WIDE   = DEF_BASE_MM_WIDE
local MM_TO_INCH     = 0.0393701

-- KTUI minis face the OPPOSITE way to their transform "forward"; offset the
-- ghost facing by this when a KTUI base is detected (see refreshBaseDims).
local KTUI_FACING_OFFSET = 180

-- Drawing
local PREVIEW_HZ     = 30
local LINE_HEIGHT    = 0.20
local LINE_THICKNESS = 0.12
local COL_LEG        = { 0.20, 0.85, 0.30 }  -- active leg (green)
local COL_LEG_DONE   = { 0.12, 0.45, 0.18 }  -- committed legs (dim green)
local COL_RANGE      = { 0.55, 0.55, 0.55 }  -- grey remaining-reach circle
local COL_GHOST      = { 0.30, 0.90, 1.00 }  -- cyan destination footprint

local READOUT_FONT   = 70       -- font size of the live readout text
local VERT_RANGE     = 6        -- +/- inches shown by the 3D range column (key 3; max KT climb/drop)
local RANGE_RING_STEP = 0.5    -- vertical gap (inches) between the cylinder rings

-- Ignore a 2nd left-click within this many seconds of the previous accepted one:
-- a jittery mouse can fire a stray double-click that commits an extra step (+1").
-- Real clicks -- stepping, and the same-spot finish click -- are always well over
-- this apart, so only accidental double-clicks are swallowed.
local CLICK_DEBOUNCE_SEC = 0.2

-- A leg shorter than this (inches) counts as "no move" -> finish, not a step, and
-- the readout shows 0 additional. This is the "cancel" window: bring the ghost back
-- within this of the model to zero the next leg. Kept small (0.05") so the 0.05-0.1"
-- band is still available as a 0.1" step; also absorbs the same-spot finish residual
-- (sub-pixel / parallax off the catcher plane, ~0.000x").
local FINISH_EPS_IN = 0.05

-- --------------------------------------------------------------- constants ---
local PHASE_IDLE = "idle"
local PHASE_MOVE = "move"

-- ------------------------------------------------------------------- state ---
local phase        = PHASE_IDLE
local controlColor = nil

local baseMove     = MOVE_DEFAULT   -- the model's Move stat (inches)
local modifier     = 0              -- +/- inches from the 1/2 keys
local adjustQueue  = 0              -- queued 1/2 presses, applied in the tick loop
local usedInches   = 0              -- budget already spent (rounded up per leg)
local baseHeading  = 0              -- ghost facing (degrees; movement doesn't turn)
local facingOffset = 0
local startPos     = nil            -- Vector, where the move began
local curPos       = nil            -- Vector, current committed point (3D)
local committedLegs = {}            -- { {a=,b=}, ... }
local history      = {}
local rangeMode    = "flat"         -- "flat" circle or "3d" vertical column (key 3)
local lastLeftClickAt = -1          -- os.clock() of the last accepted left-click (debounce)

-- live preview cache
local prevRaw      = 0              -- inches of the active leg
local prevEndPos   = nil            -- Vector end of the active leg

local loopHandle    = nil
local catcherActive = false
local lastMoveKey   = nil       -- guard: only edit the catcher when the reach/centre changes
local resizeCatcher  -- fwd decl; defined with the catcher, called from tick()

-- readout
local readoutText = nil
local lastSig     = nil             -- last draw signature (skip identical frames)

-- --------------------------------------------------------------- utilities ---
local function toUnits(inches) return inches * UNITS_PER_INCH end
local function toInches(units) return units / UNITS_PER_INCH end

-- Ceil inches to the 1-decimal precision the HUD shows. Both the readout and the
-- whole-inch charge are CEILINGS -- just at different accuracy (1 vs 0 decimals) --
-- so they always agree and never grant free movement (round-to-nearest would
-- shave up to ~0.05"). The tiny epsilon only absorbs float noise on a clean whole.
local function ceilToShown(inches) return math.ceil((inches - 1e-6) * 10) / 10 end

local function headingOf(x, z) return math.deg(math.atan2(x, z)) end
local function dirFromHeading(h)
	local r = math.rad(h)
	return { x = math.sin(r), z = math.cos(r) }
end

local function msg(pc, text, col)
	if pc and Player[pc] then Player[pc].broadcast(text, col or { 1, 1, 1 }) end
end

-- Active-move registry: one Global var per player color holding the GUID of the
-- model that player is currently moving (or "" for none), so the global
-- +1"/-1"/finish/cancel game-keys can reach that model even when the cursor is
-- aimed away from it (past the click-catcher).
--
-- IMPORTANT: use PRIMITIVE string vars, never a shared table. A table stored via
-- Global.setVar is OWNED by the script that created it; another model's script
-- (or the same model after a reload()) crashes with "Attempt to perform
-- operations with resources owned by different scripts" when it re-stores it.
-- Strings are copied across scripts, so they are safe to share.
local function setActiveMove(pc, on)
	if not pc then return end
	local key = "KT_MOVE_ACTIVE_" .. pc
	if on then
		Global.setVar(key, self.getGUID())
	elseif Global.getVar(key) == self.getGUID() then
		Global.setVar(key, "")
	end
end

-- ---------------------------------------------------------------- base dims --
local function parseBaseString(s)
	local a, b = tostring(s):match("(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)")
	if a and b then return tonumber(a), tonumber(b) end
	local n = tonumber(s)
	if n then return n, n end
	return nil, nil
end

local function refreshBaseDims()
	BASE_MM_LONG, BASE_MM_WIDE = DEF_BASE_MM_LONG, DEF_BASE_MM_WIDE
	facingOffset = 0

	local ss = self.script_state
	if ss and ss ~= "" then
		local ok, data = pcall(function() return JSON.decode(ss) end)
		if ok and type(data) == "table" and type(data.base) == "table" then
			local bx = tonumber(data.base.x)
			local bz = tonumber(data.base.z)
			if bx and bx > 0 and bz and bz > 0 then
				BASE_MM_WIDE, BASE_MM_LONG = bx, bz
				facingOffset = KTUI_FACING_OFFSET
				return
			end
		end
	end

	local gmOk, gm = pcall(function() return self.getGMNotes() end)
	if gmOk and gm and gm ~= "" then
		local ok, data = pcall(function() return JSON.decode(gm) end)
		if ok and type(data) == "table" and data.Base ~= nil then
			local L, W = parseBaseString(data.Base)
			if L and W and L > 0 and W > 0 then
				BASE_MM_LONG, BASE_MM_WIDE = L, W
				return
			end
		end
	end

	local bOk, b = pcall(function() return self.getBoundsNormalized() end)
	if bOk and b and b.size and b.size.x > 0 and b.size.z > 0 then
		local wmm = b.size.x / MM_TO_INCH
		local lmm = b.size.z / MM_TO_INCH
		-- Reject a polluted read: getBoundsNormalized can balloon to the whole
		-- reach area if a leftover click-catcher BUTTON is counted in the bounds
		-- (seen on blank models). A real base -- even a winged/oval model -- is
		-- well under 120mm, so anything bigger keeps the sane default instead of
		-- an area-sized ghost.
		if wmm <= 120 and lmm <= 120 then
			BASE_MM_WIDE, BASE_MM_LONG = wmm, lmm
		end
	end
end

local function halfLong() return (BASE_MM_LONG * 0.5) * MM_TO_INCH * UNITS_PER_INCH end
local function halfWide() return (BASE_MM_WIDE * 0.5) * MM_TO_INCH * UNITS_PER_INCH end

-- Read the operative's Move stat: KTUI live state first (script_state.stats.Move),
-- then datacard GMNotes (stats.Move), else the default. This is why teams don't
-- need to set a move per operative - it comes from the datacard stat.
local function readMoveStat()
	-- 1) KTUI live state.
	local ss = self.script_state
	if ss and ss ~= "" then
		local ok, data = pcall(function() return JSON.decode(ss) end)
		if ok and type(data) == "table" and type(data.stats) == "table" then
			local v = data.stats.Move or data.stats.MOVE or data.stats.M
			local n = v and tonumber(tostring(v):match("%d+%.?%d*"))
			if n and n > 0 then return n end
		end
	end
	-- 2) datacard GMNotes.
	local gmOk, gm = pcall(function() return self.getGMNotes() end)
	if gmOk and gm and gm ~= "" then
		local ok, data = pcall(function() return JSON.decode(gm) end)
		if ok and type(data) == "table" and type(data.stats) == "table" then
			for _, key in ipairs({ "Move", "MOVE", "M", "Movement" }) do
				local v = data.stats[key]
				if v ~= nil then
					local n = tonumber(tostring(v):match("%d+%.?%d*"))
					if n and n > 0 then return n end
				end
			end
		end
	end
	return MOVE_DEFAULT
end

-- --------------------------------------------------------------- geometry ----
local function maxInches() return math.max(0, baseMove + modifier) end
local function remainingInches() return math.max(0, maxInches() - usedInches) end

-- True surface height at world (x, z): a downward physics ray that ignores the
-- moving model itself, so it sees the real table/terrain/building surface even
-- when the cursor is over the (non-collider) click-catcher. When an `aimY` is
-- given (the cursor's reported height, lifted ~0.6 by the catcher) the ray picks
-- the surface NEAREST that level, so a landing point UNDER an overhang stays on
-- the lower floor instead of snapping to the overhang's top; only when aimY is
-- omitted does it keep the legacy "highest surface" pick. Only called when the
-- cursor moves (tick's signature gate), so the cast rate stays low.
local function surfaceY(x, z, fallbackY, aimY)
	local base = (curPos and curPos.y) or self.getPosition().y
	local hits = Physics.cast({
		origin       = { x = x, y = base + 25, z = z },
		direction    = { 0, -1, 0 },
		type         = 1,   -- ray
		max_distance = 60,
	})
	local best = nil
	for _, h in ipairs(hits or {}) do
		if h.hit_object ~= self and h.point then
			if aimY == nil then
				if best == nil or h.point.y > best then best = h.point.y end
			elseif best == nil or math.abs(h.point.y - aimY) < math.abs(best - aimY) then
				best = h.point.y
			end
		end
	end
	return best or fallbackY
end

-- Active leg preview: HORIZONTAL (2D) distance from curPos toward the pointer,
-- clamped to the remaining budget. Kill Team measures the move in 2D; a vertical
-- climb/drop is a separate penalty the player applies with the 1/2 keys. The
-- ghost sits on the ACTUAL surface under its landing point (via surfaceY), so it
-- tracks terrain/buildings instead of floating on the click-catcher's plane.
local function legPreview(pointer)
	-- No budget left: freeze the ghost exactly at the current point so it doesn't
	-- bob up/down with the cursor's surface height (there is nowhere left to go).
	if remainingInches() <= 1e-6 then
		return 0, { x = curPos.x, y = curPos.y, z = curPos.z }
	end
	local dx = pointer.x - curPos.x
	local dz = pointer.z - curPos.z
	local horiz = math.sqrt(dx * dx + dz * dz)
	if horiz < 1e-6 then
		return 0, { x = curPos.x, y = surfaceY(curPos.x, curPos.z, curPos.y, curPos.y), z = curPos.z }
	end
	local d = math.min(horiz, toUnits(remainingInches()))
	local s = d / horiz
	local ex = curPos.x + dx * s
	local ez = curPos.z + dz * s
	local endPos = { x = ex, y = surfaceY(ex, ez, curPos.y, pointer.y), z = ez }
	return toInches(d), endPos
end

-- ----------------------------------------------------------------- drawing ---
local function line(a, b, color, thick)
	return {
		points    = { { a.x, a.y + LINE_HEIGHT, a.z }, { b.x, b.y + LINE_HEIGHT, b.z } },
		color     = color,
		thickness = thick or LINE_THICKNESS,
	}
end

-- Grey remaining-reach circle on the plane of the current point.
local function appendCircle(out, centre, radiusInches, color)
	local r = toUnits(radiusInches)
	if r <= 0 then return end
	local pts, steps = {}, 48
	for i = 0, steps do
		local t = (i / steps) * 2 * math.pi
		pts[#pts + 1] = { centre.x + math.cos(t) * r, centre.y + LINE_HEIGHT, centre.z + math.sin(t) * r }
	end
	table.insert(out, { points = pts, color = color, thickness = LINE_THICKNESS * 0.6 })
end

-- 3D range column (key 3): the remaining-reach circle stacked as closely spaced
-- thin rings from VERT below to VERT above the current level, joined by a few
-- vertical struts, so it reads as a cylinder while staying light. Lets the 2D
-- range be measured against the height of nearby terrain / buildings.
local function appendRangeVolume(out, centre, radiusInches, vertInches, color)
	local r = toUnits(radiusInches)
	if r <= 0 then return end
	local v    = toUnits(vertInches)
	local yc   = centre.y + LINE_HEIGHT
	local seg  = 32
	local step = toUnits(RANGE_RING_STEP)
	if step <= 0 then step = toUnits(0.5) end
	local y = yc - v
	while y <= yc + v + 1e-6 do
		local pts = {}
		for i = 0, seg do
			local t = (i / seg) * 2 * math.pi
			pts[#pts + 1] = { centre.x + math.cos(t) * r, y, centre.z + math.sin(t) * r }
		end
		table.insert(out, { points = pts, color = color, thickness = LINE_THICKNESS * 0.6 })
		y = y + step
	end
	local struts = 16
	for i = 0, struts - 1 do
		local t = (i / struts) * 2 * math.pi
		local x = centre.x + math.cos(t) * r
		local z = centre.z + math.sin(t) * r
		table.insert(out, { points = { { x, yc - v, z }, { x, yc + v, z } }, color = color, thickness = LINE_THICKNESS * 0.6 })
	end
end

-- Corridor for one leg: centre line + two parallel edges offset by half the base
-- width, so the path shows the swept SIDES of the base (not just the centre).
local function appendLegCorridor(out, a, b, color)
	table.insert(out, line(a, b, color))
	local dx, dz = b.x - a.x, b.z - a.z
	local len = math.sqrt(dx * dx + dz * dz)
	if len < 1e-6 then return end
	local sx, sz = -dz / len, dx / len          -- unit perpendicular
	local hw = halfWide()
	local aL = { x = a.x + sx * hw, y = a.y, z = a.z + sz * hw }
	local bL = { x = b.x + sx * hw, y = b.y, z = b.z + sz * hw }
	local aR = { x = a.x - sx * hw, y = a.y, z = a.z - sz * hw }
	local bR = { x = b.x - sx * hw, y = b.y, z = b.z - sz * hw }
	table.insert(out, line(aL, bL, color, LINE_THICKNESS * 0.7))
	table.insert(out, line(aR, bR, color, LINE_THICKNESS * 0.7))
end

-- Closed oval base outline centred at (cx,cy,cz). No facing marker - a normal
-- move doesn't care about rotation.
local function appendGhost(out, cx, cy, cz, heading, color)
	local aLong = halfLong()
	local bWide = halfWide()
	local fdir  = dirFromHeading(heading)
	local sdir  = dirFromHeading(heading + 90)
	local pts, steps = {}, 40
	for i = 0, steps do
		local t  = (i / steps) * 2 * math.pi
		local fl = aLong * math.cos(t)
		local sl = bWide * math.sin(t)
		table.insert(pts, {
			cx + fdir.x * fl + sdir.x * sl,
			cy + LINE_HEIGHT,
			cz + fdir.z * fl + sdir.z * sl,
		})
	end
	table.insert(out, { points = pts, color = color or COL_GHOST, thickness = LINE_THICKNESS * 0.8 })
end

local function redraw(active, endPos)
	local lines = {}
	for _, leg in ipairs(committedLegs) do
		appendLegCorridor(lines, leg.a, leg.b, COL_LEG_DONE)
	end
	for _, l in ipairs(active or {}) do table.insert(lines, l) end
	if endPos then
		appendGhost(lines, endPos.x, endPos.y, endPos.z, baseHeading)
	end
	Global.setVectorLines(lines)
end

local function clearPreview() Global.setVectorLines({}) end

-- --------------------------------------------------- distance readout (HUD) --
-- A screen-space, top-centre readout via Global.UI. Unlike a world 3DText it is
-- NEVER hidden by terrain and is NOT written to chat. One row per player colour,
-- coloured to that player, so simultaneous moves stack (blue + red, ...) and
-- every player can read them.
--
-- Global.UI is shared, and setXml REPLACES it wholesale; another feature
-- (Chapter Tactics' fr_info_panel) also uses it. So we APPEND our container to
-- whatever UI already exists (never clobber it) and re-append if it goes
-- missing. Per-row updates use setAttribute/setValue, which don't replace the UI.
local HUD_COLORS = { "White", "Brown", "Red", "Orange", "Yellow",
                     "Green", "Teal", "Blue", "Purple", "Pink" }

local function hudColorHex(c)
	local col = Color.fromString(c)
	if not col then return "#FFFFFF" end
	-- Lighten toward white so darker player colours stay readable via the outline.
	col = col:lerp(Color.White, 0.25)
	return "#" .. col:toHex(false)
end

local function buildHudXml()
	-- Bare outlined text per colour (no background box, so it hugs the value and
	-- can't stretch). A strong black outline keeps it readable over any terrain.
	-- The layout forces each text to the container width and centres it, so it
	-- always renders (a width-less Text can collapse to nothing in a layout).
	local rows = ""
	for _, c in ipairs(HUD_COLORS) do
		rows = rows .. string.format(
			'<Text id="ktmove_txt_%s" active="false" color="%s" fontSize="26" '
			.. 'fontStyle="Bold" alignment="Center" preferredHeight="32" '
			.. 'outline="#000000" outlineSize="2 -2" raycastTarget="false"> </Text>', c, hudColorHex(c))
	end
	return '<Panel id="ktmove_hud" active="true" rectAlignment="UpperCenter" '
		.. 'width="600" height="120" offsetXY="0 -80" color="#00000000" raycastTarget="false">'
		.. '<VerticalLayout childAlignment="UpperCenter" childForceExpandWidth="true" '
		.. 'childForceExpandHeight="false" spacing="2" raycastTarget="false">'
		.. rows
		.. '</VerticalLayout></Panel>'
end

-- Ensure our HUD container exists in the (possibly shared) Global UI WITHOUT
-- wiping anything else already there. Called at move start (once), not per frame.
local function ensureHud()
	local cur = ""
	pcall(function() cur = Global.UI.getXml() or "" end)
	if type(cur) ~= "string" then cur = "" end
	if cur:find("ktmove_hud", 1, true) then return end
	pcall(function() Global.UI.setXml(cur .. buildHudXml()) end)
end

local function hudShow(color, text)
	if not color then return end
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "true")
		Global.UI.setValue("ktmove_txt_" .. color, text or " ")
	end)
end

local function hudHide(color)
	if not color then return end
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "false")
		Global.UI.setValue("ktmove_txt_" .. color, " ")
	end)
end

-- ------------------------------------------------------------- update loop ---
local function tick()
	if phase ~= PHASE_MOVE or not controlColor then return end

	-- Drain queued 1/2 budget presses. The key handler only ADDS to the queue
	-- (cheapest possible), so no press is ever lost even when hit faster than the
	-- frame rate; here we apply the whole accumulated total at once.
	if adjustQueue ~= 0 then
		local applied = adjustQueue
		if maxInches() + applied < usedInches then
			applied = usedInches - maxInches()
		end
		modifier = modifier + applied
		adjustQueue = 0
	end

	local pointer = Player[controlColor].getPointerPosition()
	if not pointer then return end
	resizeCatcher()   -- match the catch area to the CURRENT leg's remaining reach (no-op unless it changed)

	-- Skip the whole rebuild when nothing that affects the drawing changed
	-- (pointer still + no budget / leg / mode change). This keeps the tool light
	-- instead of re-sending all vector lines and text every frame.
	-- With no budget left the ghost is frozen at curPos (see legPreview), so drop
	-- the pointer from the signature: roaming the cursor over terrain of different
	-- heights must NOT rebuild the draw or make the ghost bob up/down.
	local px, py, pz = pointer.x, pointer.y, pointer.z
	if remainingInches() <= 1e-6 then px, py, pz = 0, 0, 0 end
	local sig = string.format("%.2f_%.2f_%.2f_%d_%d_%s_%d",
		px, py, pz, usedInches, modifier, rangeMode, #committedLegs)
	if sig == lastSig then return end
	lastSig = sig

	local active = {}
	readoutText = nil

	-- Remaining-reach range from the current point (flat circle, or a 3D column).
	-- Range shows where the base EDGE can reach: the centre's travel budget plus
	-- the base half-length, so the ring lands at the operative's max footprint
	-- rather than where the centre stops.
	local reach = remainingInches() + toInches(halfLong())
	if rangeMode == "3d" then
		appendRangeVolume(active, curPos, reach, VERT_RANGE, COL_RANGE)
	else
		appendCircle(active, curPos, reach, COL_RANGE)
	end

	local raw, e = legPreview(pointer)
	prevRaw, prevEndPos = raw, e
	appendLegCorridor(active, curPos, e, COL_LEG)

	-- Live total shows the distance CEIL'd to one decimal (committed whole inches +
	-- the current leg). A leg below FINISH_EPS_IN reads as 0 here because a click
	-- there FINISHES (no step), so a sub-threshold hover doesn't look like it costs
	-- the next whole inch -- you can bring the ghost back onto the model to cancel.
	local legShown = (raw < FINISH_EPS_IN) and 0 or ceilToShown(raw)
	local liveTotal = usedInches + legShown
	readoutText = string.format('%.1f" / %d"', liveTotal, maxInches())
		.. (modifier ~= 0 and string.format(" (%+d)", modifier) or "")

	redraw(active, e)
	hudShow(controlColor, readoutText)
end

local function startLoop()
	if loopHandle then return end
	loopHandle = Wait.time(tick, 1 / PREVIEW_HZ, -1)
end

local function stopLoop()
	if loopHandle then
		Wait.stop(loopHandle)
		loopHandle = nil
	end
end

-- --------------------------------------------------------- click catcher ----
-- A transparent button pinned to the model, covering the CURRENT leg's reach (a
-- disc of radius = REMAINING budget + margin, centred on curPos). LEFT-click =
-- step, RIGHT-click = undo. Because it is a button ON the model, hovering it
-- counts as hovering the model, so the number ROW works with no binding. It only
-- locks that small area (not the table); as you spend budget it re-centres on
-- the new point and shrinks to what's left, so it never claims more than needed.

-- Half-reach (inches) of the catch disc for the CURRENT leg: remaining budget +
-- margin, floored so a nearly-spent move still has a clickable area.
local function catcherReachIn()
	local r = remainingInches() + CATCHER_MARGIN_IN
	return (r < 3) and 3 or r
end

local function catcherKey()
	if not curPos then return "none" end
	return string.format("%.2f:%.2f:%.2f", curPos.x, curPos.z, catcherReachIn())
end

-- Remove every catcher button currently on the model. Collect indices first and
-- remove high->low: removeButton(index) reshuffles the remaining indices, so
-- removing while iterating by index can skip a button (leaving a stale catcher).
local function clearCatcherButtons()
	local idx = {}
	for _, b in ipairs(self.getButtons() or {}) do
		if b.click_function == "moveCatcherClick" then idx[#idx + 1] = b.index end
	end
	table.sort(idx, function(a, b) return a > b end)
	for _, i in ipairs(idx) do self.removeButton(i) end
end

-- (Re)create the catcher as a FRESH button at the model CENTRE, sized to the
-- current leg's remaining reach. The model steps to each committed leg (see
-- commitLeg), so a CENTRED button always sits on the operative's current spot --
-- rotation/scale-proof, no offset math, and the catch area stays the reachable
-- bubble. We remove+recreate rather than editButton because editing a button's
-- size/position does not reliably rebuild its invisible click hitbox in TTS.
local function placeCatcher()
	clearCatcherButtons()
	local sc   = self.getScale()
	local span = 2 * catcherReachIn() * CATCHER_UNITS_PER_IN
	self.createButton({
		click_function = "moveCatcherClick",
		function_owner = self,
		label          = "",
		position       = { 0, 0.6 / (sc.y ~= 0 and sc.y or 1), 0 },
		rotation       = { 0, 0, 0 },
		width          = span / (sc.x ~= 0 and sc.x or 1),
		height         = span / (sc.z ~= 0 and sc.z or 1),
		font_size      = 100,
		color          = { 0, 0, 0, 0 },
		tooltip        = "Left: step (double=finish)  Right: undo  1:-1\"  2:+1\"  3:3D range  0:cancel",
	})
end

local function createCatcher()
	if catcherActive then return end
	placeCatcher()
	catcherActive = true
	lastMoveKey   = catcherKey()
end

-- Re-centre + resize the catcher to the CURRENT leg's reachable area (a disc of
-- radius = remaining budget around curPos). Guarded so it only rebuilds when the
-- reach/centre actually changes (a leg commits, a 1/2 budget change, or a
-- step-back), never per frame -- so there is no cursor-follow lag. Assigns the
-- forward-declared upvalue so tick() (defined earlier) can call it.
resizeCatcher = function()
	if not catcherActive or not curPos then return end
	local key = catcherKey()
	if key == lastMoveKey then return end   -- nothing changed -> no rebuild (no lag)
	lastMoveKey = key
	placeCatcher()
end

local function removeCatcher()
	if not catcherActive then return end
	clearCatcherButtons()
	catcherActive = false
end

-- ------------------------------------------------------------ history/undo ---
local function pushHistory()
	table.insert(history, {
		pos      = { x = curPos.x, y = curPos.y, z = curPos.z },
		used     = usedInches,
		modifier = modifier,
		legs     = #committedLegs,
	})
end

local function restoreFrom(s)
	curPos      = { x = s.pos.x, y = s.pos.y, z = s.pos.z }
	-- Move the model back to the restored point (it steps with each leg).
	self.setPosition({ curPos.x, curPos.y, curPos.z })
	usedInches  = s.used
	modifier    = s.modifier
	while #committedLegs > s.legs do table.remove(committedLegs) end
end

-- ------------------------------------------------------------ state changes --
local function applyToModel()
	local r = self.getRotation()
	self.setPosition({ curPos.x, curPos.y, curPos.z })
	self.setRotation({ r.x, r.y, r.z })   -- movement doesn't change facing
end

local function finishMove(pc, text)
	stopLoop()
	clearPreview()
	removeCatcher()
	hudHide(pc or controlColor)
	setActiveMove(pc or controlColor, false)
	applyToModel()
	msg(pc, text or string.format('Move complete: %d" used.', usedInches), COL_LEG)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

local function cancelMove(pc)
	stopLoop()
	clearPreview()
	removeCatcher()
	hudHide(pc or controlColor)
	setActiveMove(pc or controlColor, false)
	-- Return the model to where the move began (it steps with each committed leg).
	if startPos then self.setPosition({ startPos.x, startPos.y, startPos.z }) end
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
	if pc then msg(pc, "Move cancelled.", COL_RANGE) end
end

-- A quiet teardown for when the player physically PICKS UP the model mid-move:
-- stop the preview, drop the HUD/catcher and clear the active flag, but DON'T
-- snap the model back and DON'T broadcast a "cancelled" message -- the pickup is
-- a deliberate manual reposition, not a cancel, so it shouldn't give false
-- "Move cancelled" feedback.
local function abortMove()
	stopLoop()
	clearPreview()
	removeCatcher()
	hudHide(controlColor)
	setActiveMove(controlColor, false)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

local function beginMove(pc, forcedBase)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startPos     = { x = p.x, y = p.y, z = p.z }
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	baseHeading  = headingOf(fwd.x, fwd.z) + facingOffset
	baseMove     = forcedBase or readMoveStat()
	modifier     = 0
	adjustQueue  = 0
	usedInches   = 0
	rangeMode    = "flat"
	committedLegs = {}
	history      = {}
	lastSig      = nil
	lastLeftClickAt = -1
	phase        = PHASE_MOVE
	startLoop()
	createCatcher()
	ensureHud()
	setActiveMove(pc, true)
end

local function commitLeg(rawIn, endPos)
	if rawIn <= 1e-6 then return false end
	pushHistory()
	table.insert(committedLegs, {
		a = { x = curPos.x, y = curPos.y, z = curPos.z },
		b = { x = endPos.x, y = endPos.y, z = endPos.z },
	})
	usedInches = usedInches + math.ceil(ceilToShown(rawIn) - 1e-6)
	curPos     = { x = endPos.x, y = endPos.y, z = endPos.z }
	-- Step the model to the committed point so the (centred) catcher rides with
	-- it -- keeps the catch area on the operative's real spot, rotation-proof.
	self.setPosition({ curPos.x, curPos.y, curPos.z })
	-- Each committed step lands flat; the next increment starts in 2D again.
	-- (3D is only needed while measuring a climb/drop; re-toggle with 3 if so.)
	rangeMode  = "flat"
	return true
end

-- LEFT-click: commit the current leg and start the next. A click that would
-- commit a ZERO-length leg finishes the move instead - this happens when the
-- budget is spent (ghost can't advance) or when you click again without moving
-- the cursor (a "double-click" to confirm). Recompute from the live pointer so a
-- double-click faster than a tick still reads the true leg length.
local function advance(pc)
	local pointer = Player[pc] and Player[pc].getPointerPosition()
	if pointer then
		local raw, e = legPreview(pointer)
		prevRaw, prevEndPos = raw, e
	end
	if not prevEndPos then return end
	if prevRaw < FINISH_EPS_IN then
		-- Finish only if we've already moved or the budget is spent; otherwise
		-- ignore, so a stray click at the very start doesn't end the move instantly.
		if #committedLegs > 0 or remainingInches() <= 0 then
			finishMove(pc, string.format('Move complete: %d" used.', usedInches))
		end
		return
	end
	commitLeg(prevRaw, prevEndPos)
end

-- RIGHT-click: undo the last leg (or cancel from the first).
local function stepBack(pc)
	if #history == 0 then
		cancelMove(pc)
		return
	end
	local s = table.remove(history)
	restoreFrom(s)
	msg(pc, "Stepped back.", COL_LEG)
end

-- Key 9: commit the current leg (if any) and finish.
local function finishNow(pc)
	if prevEndPos then commitLeg(prevRaw, prevEndPos) end
	finishMove(pc, string.format('Move complete: %d" used.', usedInches))
end

-- Handle a number key. IMPORTANT: TTS can merge rapid same-key presses on the
-- number row into a single multi-digit number (two quick 1s arrive as 11), so
-- for the budget keys we DECOMPOSE the number into its digits and queue each one
-- (11 -> two -1; 12 -> -1 then +1). The tick loop applies the summed total, so
-- no press is lost no matter how fast you tap. 1 = -1", 2 = +1".
local function handleDigit(pc, number)
	if phase ~= PHASE_MOVE then return false end
	if controlColor and pc ~= controlColor then return false end
	-- Deliberate single-press commands.
	if number == 3 then
		rangeMode = (rangeMode == "3d") and "flat" or "3d"
		return true
	elseif number == 9 then
		finishNow(pc)
		return true
	elseif number == 0 then
		cancelMove(pc)
		return true
	end
	local matched = false
	for d in tostring(number):gmatch("%d") do
		if d == "1" then adjustQueue = adjustQueue - 1; matched = true
		elseif d == "2" then adjustQueue = adjustQueue + 1; matched = true end
	end
	return matched
end

-- ----------------------------------------------------------------- wiring ----
-- Invisible catcher handler. altClick == true means a right-click (undo).
function moveCatcherClick(_, playerColor, altClick)
	if phase ~= PHASE_MOVE then return end
	if controlColor and playerColor ~= controlColor then return end
	if altClick then
		stepBack(playerColor)
	else
		-- Debounce accidental double-clicks (jittery mice): swallow a left-click that
		-- lands within CLICK_DEBOUNCE_SEC of the last accepted one so it can't eat an
		-- extra step. Intentional step/finish clicks are always well over this apart.
		local now = os.clock()
		if now - lastLeftClickAt < CLICK_DEBOUNCE_SEC then return end
		lastLeftClickAt = now
		advance(playerColor)
	end
end

function moveScriptingButton(index, playerColor)
	handleDigit(playerColor, index == 10 and 0 or index)
end

-- Hotkey entry point (called on the HOVERED model by the global hotkey below).
function moveHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginMove((params or {}).color) end
end

-- Dash is identical to Move but always starts from a fixed DASH_INCHES budget
-- instead of the model's Move stat.
function dashHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginMove((params or {}).color, DASH_INCHES) end
end

-- Per-action entry points for the global game-keys, called on the active-move
-- model. The +/-1" nudges only ADD to the per-tick queue (like the number keys),
-- so presses are coalesced and applied once per tick (no redraw-per-press cost),
-- yet each press is captured instantly (no number-row multi-digit input wait).
function moveAdjustPlus(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	adjustQueue = adjustQueue + 1
end

function moveAdjustMinus(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	adjustQueue = adjustQueue - 1
end

function moveFinishHotkey(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	finishNow(pc)
end

function moveCancelHotkey(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	cancelMove(pc)
end

function moveToggleRangeHotkey(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	rangeMode = (rangeMode == "3d") and "flat" or "3d"
end

-- Resolve the model a player is currently moving: prefer the active-move
-- registry (works even when the cursor is aimed away from it), fall back to the
-- hovered object.
local function moveAdjustDispatch(color, hovered, fn)
	local obj = nil
	local guid = Global.getVar("KT_MOVE_ACTIVE_" .. color)
	if type(guid) == "string" and guid ~= "" then obj = getObjectFromGUID(guid) end
	if obj == nil and hovered ~= nil and hovered.call ~= nil then obj = hovered end
	if obj ~= nil and obj.call ~= nil then obj.call(fn, { color = color }) end
end

function setupMoveTool()
	self.addContextMenuItem("Move", function(pc)
		if phase == PHASE_IDLE then beginMove(pc) end
	end, false)
	self.addContextMenuItem("Dash", function(pc)
		if phase == PHASE_IDLE then beginMove(pc, DASH_INCHES) end
	end, false)
	-- Optional keyboard shortcuts. Registered ONCE globally (guarded via Global
	-- vars) so they aren't re-registered by every model; each callback starts the
	-- action on whatever model the player is HOVERING. Bind keys under
	-- Options -> Controls -> Game Keys ("KT: Move/Dash (hovered model)").
	if Global.getVar("KT_MOVE_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_HOTKEY", true)
		addHotkey("KT: Move (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("moveHotkeyTrigger", { color = color })
			end
		end, false)
	end
	if Global.getVar("KT_DASH_HOTKEY") ~= true then
		Global.setVar("KT_DASH_HOTKEY", true)
		addHotkey("KT: Dash (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("dashHotkeyTrigger", { color = color })
			end
		end, false)
	end
	-- Per-action game-keys (instant, rebindable). They feed the SAME per-tick queue
	-- as the number keys and reach the active-move model via the registry, so
	-- binding them sidesteps the number row's built-in multi-digit input wait.
	if Global.getVar("KT_MOVE_PLUS_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_PLUS_HOTKEY", true)
		addHotkey("KT: Move +1 inch", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveAdjustPlus")
		end, false)
	end
	if Global.getVar("KT_MOVE_MINUS_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_MINUS_HOTKEY", true)
		addHotkey("KT: Move -1 inch", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveAdjustMinus")
		end, false)
	end
	if Global.getVar("KT_MOVE_FINISH_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_FINISH_HOTKEY", true)
		addHotkey("KT: Move finish", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveFinishHotkey")
		end, false)
	end
	if Global.getVar("KT_MOVE_CANCEL_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_CANCEL_HOTKEY", true)
		addHotkey("KT: Move cancel", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveCancelHotkey")
		end, false)
	end
	if Global.getVar("KT_MOVE_RANGE_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_RANGE_HOTKEY", true)
		addHotkey("KT: Move toggle 3D range", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveToggleRangeHotkey")
		end, false)
	end
end

function moveOnPickUp(playerColor)
	-- A manual pickup is NOT a cancel: tear down the preview/HUD/catcher quietly
	-- and leave the model where the player drops it (no snap-back, no callout).
	if phase ~= PHASE_IDLE then abortMove() end
end

local _move_prev_onLoad = onLoad
function onLoad(...)
	-- pcall-guard the host's onLoad: a broken host extender (e.g. a third-party
	-- KTUI / Command Node extender that errors inside its own refreshUI) must not
	-- abort loading and drop the Move tool. Our setup always runs; the host keeps
	-- whatever it managed to complete before the error.
	if _move_prev_onLoad then pcall(_move_prev_onLoad, ...) end
	setupMoveTool()
end

local _move_prev_onPickUp = onPickUp
function onPickUp(...)
	if _move_prev_onPickUp then _move_prev_onPickUp(...) end
	moveOnPickUp(...)
end

local _move_prev_onScriptingButtonDown = onScriptingButtonDown
function onScriptingButtonDown(...)
	if _move_prev_onScriptingButtonDown then _move_prev_onScriptingButtonDown(...) end
	moveScriptingButton(...)
end

local _move_prev_onNumberTyped = onNumberTyped
function onNumberTyped(playerColor, number, alt)
	if phase ~= PHASE_IDLE and (not controlColor or playerColor == controlColor) then
		handleDigit(playerColor, number)
		return true
	end
	if _move_prev_onNumberTyped then return _move_prev_onNumberTyped(playerColor, number, alt) end
end
]=]

SPRINT_TOOL_CODE = [=[--[[ ============================================================================
  SPRINT MOVEMENT TOOL  (Proof of Concept, v2)
  For the Exodite Dragon Masters (Draconic Steeds) team.

  What a sprint is
  ----------------
  A sprint is up to two STRAIGHT legs with a SINGLE pivot between (or before)
  them. The straight distance travelled is capped at 9" total; pivots are free
  and limited to +/-45 degrees. Unlike the standard KT move tool, direction is
  locked to the model's facing and turns only happen at the one allowed pivot.

  Legal shapes
  ------------
    * move                      (one straight leg, < 9", no pivot)
    * move -> pivot -> move      (classic: turn once mid-sprint)
    * move -> pivot              (first leg used 8-9", no budget left to move on)
    * pivot -> move              (pivot BEFORE moving, then up to 9" straight)
  Only ONE pivot is ever allowed. Straight legs count toward the 9" budget
  (each rounded UP to the whole inch when spent); pivots cost nothing.

  Controls
  --------
  Number input works two ways, with NO key binding needed either way:
    * NUMPAD - TTS "scripting buttons" (which default to the numpad); these
      fire anywhere, even while aiming at the table.
    * Number ROW - via onNumberTyped, which fires while your pointer is over
      the model. During a sprint the invisible click catcher covers the travel
      corridor, so the row registers anywhere the model could move.
  While a sprint is active, for the driving player:
    1 = straight move            (first step only)
    2 = pivot from FRONT of base
    3 = pivot from CENTRE of base
    4 = pivot from BACK of base
    9 = confirm / finish straight, no (further) pivot
    0 = cancel the whole sprint  (any step)
  (9 and 0 are used for finish/cancel - kept apart from the 1-4 mode keys so
   they aren't hit by accident, matching the standard move tool.)
  Mouse (via an invisible click catcher pinned to the model):
    LEFT-click  = apply / commit the current step (and advance)
    RIGHT-click = step back one (undo), or cancel from the first step
  You aim with your pointer the whole time; the click is captured at your
  current aim point so the distance/angle you see is what you get.

  Straight steps support BACKWARD movement: drag the line behind the model to
  reverse. Backward is capped at 3" total for the whole sprint (forward still
  uses the separate 9" budget).

  Step flow
  ---------
    idle --Begin--> S1 --(straight)--> PIVOT --(pivot)--> S2 --(straight)--> done
                       \--(pivot first)------------------> S2 --------------> done
  * S1  : default straight; press 2/3/4 to make it a pivot, 1 to go back to
          straight. Left-click commits. If committed straight -> PIVOT step.
          If committed as a pivot (pivot-first) -> jumps straight to S2.
  * PIVOT: press 2/3/4 to choose the pivot anchor, drag to turn (+/-45deg).
          Left-click commits -> S2 (or finishes if <1" budget remains).
          Press 9 here to finish with NO pivot (just the first leg) - e.g. a
          short 2" straight shuffle and done.
  * S2  : straight only. Left-click (or 9) finishes. Right-click backs up.

  Preview
  -------
  Each straight leg is drawn as a corridor: a centre line plus two parallel
  edge lines offset by half the base width, showing the swept path of the base.
  A cyan ghost of the base (oval) is drawn at the destination, oriented to the
  final heading, so you can see exactly where the model lands.

  Injection-safe loading
  -----------------------
  This file can be APPENDED to a model that already has its own script (e.g. a
  KTUI mini) without breaking it:
    * onLoad / onPickUp / onScriptingButtonDown / onNumberTyped are CHAINED
      (host runs first).
    * It never WRITES self.script_state, so saved state (wounds, roles, base,
      etc.) is untouched. It only READS script_state to size the base ghost.
    * The click catcher is a transparent button pinned to the model, sized to
      just past the reach (not the whole table), and removed by its own
      click_function so it never calls clearButtons().
    * Globals it adds are uniquely named (setupSprintTool, sprintOnPickUp,
      sprintCatcherClick, sprintScriptingButton + chained handlers).

  Assumes 1 TTS unit = 1 inch (KT-UI table convention). Change UNITS_PER_INCH
  if your table scale differs. POC: uses Global vector lines, so run one sprint
  at a time.
============================================================================ ]]

-- ------------------------------------------------------------------ tuning ---
local MAX_INCHES     = 9        -- total straight distance cap
local MAX_PIVOT_DEG  = 45       -- max single turn, left or right
local MAX_BACK_INCHES = 3       -- total BACKWARD straight distance cap
local UNITS_PER_INCH = 1        -- world units per inch (KT-UI table = 1)

-- Click-catcher: a transparent button pinned to the model, covering ONLY the area
-- the model can actually travel this step -- a NARROW rectangle aligned to the
-- model's facing that runs the forward budget (+ margin) ahead and the backward
-- budget (+ margin) behind, base-width wide. Because it is a button ON the model,
-- hovering it counts as hovering the model, so the number ROW (onNumberTyped)
-- works across the reach with NO key binding. It locks only this slim corridor,
-- not a big disc over the whole table. It is rebuilt ONLY when the reach changes
-- (a leg is committed or a step-back happens), NOT every frame -- so no lag.
local CATCHER_MARGIN_IN    = 2           -- inches of catch area past the reach (~1" felt short at 1)
local CATCHER_SIDE_MARGIN_IN = 2.5       -- inches of catch area either side of the base (corridor width)
-- button-units per inch. TUNING KNOB: raise = bigger catcher, lower = smaller.
-- (14000/9 rendered ~2-3x too wide -- 30" for a ~10" reach; ~450 targets it.)
local CATCHER_UNITS_PER_IN = 450

-- Leap (Exodite special move): reposition the base freely by aiming, with FREE
-- 360 rotation, clamped so ANY part of the base stays within MAX_LEAP_INCHES of
-- ANY part of the original footprint (edge-to-edge gap). Rotation is STEPPED:
-- each tap of 1/2 (numpad OR number row) turns the base LEAP_ROT_STEP degrees.
-- Taps are BATCHED: every tap adds/subtracts one step to a pending counter that
-- is flushed to curHeading on the next preview tick, so rapid taps within a
-- frame all count (n taps = n steps) instead of being swallowed. This keeps the
-- turn smooth regardless of how fast you tap.
local MAX_LEAP_INCHES   = 1     -- max edge-to-edge gap from the original base
local LEAP_ROT_STEP     = 5     -- degrees turned per 1/2 tap (numpad or number row)
local LEAP_STEPS        = 32    -- oval perimeter samples for the gap clamp

-- Pivot/Turn aiming: how far past +/-45deg the pointer may stray before the
-- ghost hides (so aiming behind the model doesn't snap to a weird 45deg turn).
local PIVOT_AIM_TOL = 22        -- degrees of tolerance outside the turn cone

-- Live distance/angle readout drawn as a 3DText object near the ghost.
local READOUT_FONT  = 70        -- font size of the readout text

-- Default base footprint (mm), used only when a model exposes NO base metadata.
-- Long axis (z) runs along the model's facing. The tool prefers each model's
-- ACTUAL base: KTUI script_state.base, then datacard GMNotes "Base", then the
-- physical footprint (so models with different base sizes all work).
local DEF_BASE_MM_LONG = 75     -- oval length (front-to-back), mm
local DEF_BASE_MM_WIDE = 42     -- oval width (side-to-side), mm
local BASE_MM_LONG   = DEF_BASE_MM_LONG
local BASE_MM_WIDE   = DEF_BASE_MM_WIDE
local MM_TO_INCH     = 0.0393701

-- Baseline facing offset (degrees) added to a KTUI mini's transform-forward.
-- The common/correct Exodite sculpts run head-first at 0, so the default is 0.
-- Mirrored/alternate models come out reversed -- the player flips them with the
-- "Rotate base 90" menu item, which stores a per-model kt_front (e.g. 180) that
-- is ADDED to this. Plain objects (no KTUI base) always use 0.
local KTUI_FACING_OFFSET = 0

-- Drawing
local PREVIEW_HZ     = 60       -- preview / rotation refresh rate (Hz)
local LINE_HEIGHT    = 0.20     -- how high above the base to draw the preview
local LINE_THICKNESS = 0.12
local COL_LEG        = { 0.20, 0.85, 0.30 }  -- active leg / corridor (green)
local COL_LEG_DONE   = { 0.12, 0.45, 0.18 }  -- already-committed legs (dim)
local COL_PIVOT      = { 1.00, 0.75, 0.10 }  -- amber pivot marker / prompts
local COL_LIMIT      = { 0.55, 0.55, 0.55 }  -- grey +/-45 guide lines
local COL_GHOST      = { 0.30, 0.90, 1.00 }  -- cyan destination footprint
local COL_ORIG       = { 0.55, 0.55, 0.55 }  -- grey original footprint (Leap)

-- --------------------------------------------------------------- constants ---
local PHASE_IDLE  = "idle"
local PHASE_S1    = "s1"        -- first step: straight OR pivot (mode-selectable)
local PHASE_PIVOT = "pivot"     -- middle step: pivot only
local PHASE_S2    = "s2"        -- last step: straight only
local PHASE_LEAP  = "leap"      -- Exodite Leap: free reposition + free rotate

-- ------------------------------------------------------------------- state ---
local phase        = PHASE_IDLE
local controlColor = nil        -- player driving the current sprint

-- committed cumulative transform (updated as each step is applied)
local startY       = 0          -- model Y (kept constant)
local startPos     = nil        -- where the sprint began (for cancel restore)
local startHeading = nil        -- visual heading at the start (for cancel restore)
local curPos       = nil        -- Vector, committed planar position
local curHeading   = 0          -- committed heading (degrees)
local spentInches  = 0          -- straight budget already used (rounded up)
local backSpent    = 0          -- BACKWARD straight distance used (raw inches)
local rawStraight  = 0          -- exact straight distance travelled (for readout)
local facingOffset = 0          -- deg added to transform-forward -> visual facing
local committedLegs = {}         -- { {a=,b=,heading=}, ... } straight corridors

-- current step's selected mode
--   S1:    "straight" | "pivotFront" | "pivotCenter" | "pivotBack"
--   PIVOT: pivotOrigin is used instead ("front" | "center" | "back")
local s1Mode       = "straight"
local pivotOrigin  = "center"
local turnOnly     = false      -- "Turn" action: a single pivot, no movement
local history      = {}

-- Leap state (Exodite special move)
local leapOrig        = nil     -- original planar centre {x,z} (fixed anchor)
local leapOrigHeading = 0       -- original heading (the footprint doesn't turn)
local leapOrigPts     = nil     -- cached original oval perimeter points
local leapPendingRot  = 0       -- net rotation steps tapped since the last tick
                                -- (+ = clockwise, - = anticlockwise); flushed in tick()

-- Live readout (distance/angle) shown as a screen-space HUD (Global.UI), shared
-- with the Move tool via the same ktmove_hud container, so it never occludes
-- terrain and always renders top-centre in the driving player's colour.
local readoutText    = nil      -- text to show this tick (nil = hide)
local readoutPos     = nil      -- world {x,z} of the measurement (unused by the HUD)

-- live preview cache (refreshed every tick; used by commit/confirm)
local prevStraight = 0          -- signed inches of the active straight leg
local prevEndPos   = nil        -- Vector end of the active preview
local prevHeading  = 0          -- heading at the end of the active preview

local loopHandle    = nil
local lastReport    = nil
local catcherActive = false
local catcherTooltip = nil       -- tooltip for the current catcher (varies by Sprint/Turn/Leap)
local lastCatcherKind = nil      -- guard: pivot(true)/straight(false) shape currently built
local lastCatcherFwd  = nil      -- guard: only rebuild the catcher when the reach changes
local lastCatcherBack = nil      -- guard: only rebuild the catcher when the reach changes
local syncCatcher                -- fwd decl; defined with the catcher, called from tick()
local applyToModel               -- fwd decl; steps/rotates the model to the current leg

-- --------------------------------------------------------------- utilities ---
local function toUnits(inches) return inches * UNITS_PER_INCH end
local function toInches(units) return units / UNITS_PER_INCH end

-- Ceil inches to the 1-decimal precision the HUD shows. The readout and the
-- whole-inch charge (spentInches ceil) are both CEILINGS -- just at different
-- accuracy (1 vs 0 decimals) -- so they always agree and never grant free
-- movement. The tiny epsilon only absorbs float noise on a clean whole value.
-- (Backward travel is raw-tracked/capped, so it keeps its raw readout.)
local function ceilToShown(inches) return math.ceil((inches - 1e-6) * 10) / 10 end

-- Heading (degrees) of a planar vector, matching TTS yaw: forward = (sin,0,cos)
local function headingOf(x, z) return math.deg(math.atan2(x, z)) end

-- Unit planar direction for a given heading (degrees)
local function dirFromHeading(h)
	local r = math.rad(h)
	return { x = math.sin(r), z = math.cos(r) }
end

-- Normalise an angle difference into [-180, 180]
local function wrap180(a) return (a + 180) % 360 - 180 end

local function clamp(v, lo, hi)
	if v < lo then return lo end
	if v > hi then return hi end
	return v
end

local function msg(pc, text, col)
	if pc and Player[pc] then Player[pc].broadcast(text, col or { 1, 1, 1 }) end
end

-- Active-sprint registry: one Global var per player colour holding the GUID of
-- the model that player is currently sprinting (or "" for none), so the mode /
-- rotate / finish / cancel game-keys can reach that model even when the cursor
-- is aimed at the table, past the click catcher. PRIMITIVE strings only (a table
-- stored via Global.setVar is owned by the creating script and crashes another
-- model's script on re-store); strings copy safely across scripts.
local function setActiveSprint(pc, on)
	if not pc then return end
	local key = "KT_SPRINT_ACTIVE_" .. pc
	if on then
		Global.setVar(key, self.getGUID())
	elseif Global.getVar(key) == self.getGUID() then
		Global.setVar(key, "")
	end
end

-- Is this player currently acting on THIS model? (used to gate "Begin")
local function isTargeted(playerColor, hoveredObject)
	if hoveredObject == self then return true end
	local p = Player[playerColor]
	if not p then return false end
	for _, o in ipairs(p.getSelectedObjects() or {}) do
		if o == self then return true end
	end
	return false
end

-- ---------------------------------------------------------------- base dims --
-- Figure out the model's ACTUAL base so the ghost + corridor match it (and so
-- future models with different bases just work). Tries, in order:
--   1) KTUI live state:  script_state.base = { x = width, z = length } (mm)
--   2) datacard GMNotes: "Base" = "LxW" (oval) or a number (round), in mm
--   3) physical footprint: getBoundsNormalized() (world inches -> mm)
--   4) the DEF_BASE_MM_* fallback.
-- Only KTUI state (1) also applies the mesh-facing offset (see above).
local function parseBaseString(s)
	-- "75x42" / "75 x 42" -> length 75, width 42 ; a lone number -> round base.
	local a, b = tostring(s):match("(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)")
	if a and b then return tonumber(a), tonumber(b) end
	local n = tonumber(s)
	if n then return n, n end
	return nil, nil
end

local function refreshBaseDims()
	BASE_MM_LONG, BASE_MM_WIDE = DEF_BASE_MM_LONG, DEF_BASE_MM_WIDE
	facingOffset = 0

	-- 1) KTUI live state.
	local ss = self.script_state
	if ss and ss ~= "" then
		local ok, data = pcall(function() return JSON.decode(ss) end)
		if ok and type(data) == "table" and type(data.base) == "table" then
			local bx = tonumber(data.base.x)   -- width  (side-to-side)
			local bz = tonumber(data.base.z)   -- length (front-to-back)
			if bx and bx > 0 and bz and bz > 0 then
				BASE_MM_WIDE, BASE_MM_LONG = bx, bz
				-- Facing = transform-forward + KTUI_FACING_OFFSET (default 0, i.e.
				-- correct sculpts run head-first) + a per-model kt_front offset
				-- (0/90/180/270, cycled by the "Rotate base 90" menu item) that
				-- corrects mirrored/alternate sculpts so Sprint/Turn/Leap don't run
				-- tail-first. Absent kt_front = 0 = no change.
				local ktf = tonumber(data.kt_front) or 0
				facingOffset = KTUI_FACING_OFFSET + ktf
				-- "Rotate base 90" also SWAPS base.x/base.z in state (to rotate the
				-- KTUI ring). At odd quarters (90/270) that moves the long axis onto
				-- the OTHER dimension, so re-label LONG(front-to-back)/WIDE(side-to-
				-- side) here to keep the ghost + corridor drawn long-along-heading.
				if (math.floor(ktf / 90) % 2) == 1 then
					BASE_MM_WIDE, BASE_MM_LONG = BASE_MM_LONG, BASE_MM_WIDE
				end
				return
			end
		end
	end

	-- 2) datacard GMNotes "Base".
	local gmOk, gm = pcall(function() return self.getGMNotes() end)
	if gmOk and gm and gm ~= "" then
		local ok, data = pcall(function() return JSON.decode(gm) end)
		if ok and type(data) == "table" and data.Base ~= nil then
			local L, W = parseBaseString(data.Base)
			if L and W and L > 0 and W > 0 then
				BASE_MM_LONG, BASE_MM_WIDE = L, W
				return
			end
		end
	end

	-- 3) physical footprint (adapts to any model's real size).
	local bOk, b = pcall(function() return self.getBoundsNormalized() end)
	if bOk and b and b.size and b.size.x > 0 and b.size.z > 0 then
		BASE_MM_WIDE = b.size.x / MM_TO_INCH
		BASE_MM_LONG = b.size.z / MM_TO_INCH
	end
end

local function halfLong() return (BASE_MM_LONG * 0.5) * MM_TO_INCH * UNITS_PER_INCH end
local function halfWide() return (BASE_MM_WIDE * 0.5) * MM_TO_INCH * UNITS_PER_INCH end

-- --------------------------------------------------------------- geometry ----
local function remainingInches() return math.max(0, MAX_INCHES - spentInches) end

-- Straight leg preview from curPos along curHeading toward the pointer. Allows
-- BACKWARD movement (negative projection); magnitude clamped to the remaining
-- budget. Returns signed inches, the end Vector, and the (unchanged) heading.
local function straightPreview(pointer)
	local fdir  = dirFromHeading(curHeading)
	local px, pz = pointer.x - curPos.x, pointer.z - curPos.z
	local proj  = px * fdir.x + pz * fdir.z          -- signed world units
	local remFwdU  = toUnits(remainingInches())
	local remBackU = toUnits(math.max(0, MAX_BACK_INCHES - backSpent))
	local d        = clamp(proj, -remBackU, remFwdU)
	local endPos = { x = curPos.x + fdir.x * d, y = curPos.y, z = curPos.z + fdir.z * d }
	return toInches(d), endPos, curHeading
end

-- The fixed anchor point of a pivot for a given origin, at (pos, heading).
local function pivotAnchor(origin, pos, heading)
	local fdir = dirFromHeading(heading)
	local hl   = halfLong()
	if origin == "front" then
		return { x = pos.x + fdir.x * hl, z = pos.z + fdir.z * hl }
	elseif origin == "back" then
		return { x = pos.x - fdir.x * hl, z = pos.z - fdir.z * hl }
	end
	return { x = pos.x, z = pos.z }                  -- centre
end

-- Pivot preview: turn the facing toward the pointer, clamped to +/-45deg,
-- rotating about the chosen anchor. Aiming works in TWO cones: the FRONT cone
-- aims the front of the base at the pointer (normal turn); the BACK cone aims
-- the REAR of the base at the pointer (inverse turn), so pointing behind the
-- model turns it toward you instead of snapping to max. Between the cones (the
-- sides) there is no valid aim. Returns new heading, new centre Vector, the
-- anchor point, the signed turn delta, and whether the aim is valid.
local function pivotPreview(pointer, origin, pos, heading)
	local anchor  = pivotAnchor(origin, pos, heading)
	local desired = headingOf(pointer.x - anchor.x, pointer.z - anchor.z)
	local raw     = wrap180(desired - heading)          -- front-aim angle
	local rawBack = wrap180(raw - 180)                  -- rear-aim angle
	local base, valid
	if math.abs(raw) <= MAX_PIVOT_DEG + PIVOT_AIM_TOL then
		base, valid = raw, true                         -- front cone: aim the front
	elseif math.abs(rawBack) <= MAX_PIVOT_DEG + PIVOT_AIM_TOL then
		base, valid = rawBack, true                     -- back cone: aim the rear (inverse)
	else
		base, valid = 0, false                          -- side dead zone: no aim
	end
	local delta   = clamp(base, -MAX_PIVOT_DEG, MAX_PIVOT_DEG)
	local newH    = heading + delta
	local nfd     = dirFromHeading(newH)
	local hl      = halfLong()
	local newPos
	if origin == "front" then
		newPos = { x = anchor.x - nfd.x * hl, y = pos.y, z = anchor.z - nfd.z * hl }
	elseif origin == "back" then
		newPos = { x = anchor.x + nfd.x * hl, y = pos.y, z = anchor.z + nfd.z * hl }
	else
		newPos = { x = pos.x, y = pos.y, z = pos.z }
	end
	return newH, newPos, anchor, delta, valid
end

-- --------------------------------------------------------------------- leap ---
-- Sample the model's oval base perimeter (planar {x,z}) at a centre/heading.
-- Used to measure the edge-to-edge gap for the Leap clamp.
local function ovalPerimeter(cx, cz, heading, steps)
	local aLong = halfLong()
	local bWide = halfWide()
	local fdir  = dirFromHeading(heading)
	local sdir  = dirFromHeading(heading + 90)
	local pts = {}
	for i = 0, steps - 1 do
		local t  = (i / steps) * 2 * math.pi
		local fl = aLong * math.cos(t)
		local sl = bWide * math.sin(t)
		pts[#pts + 1] = {
			x = cx + fdir.x * fl + sdir.x * sl,
			z = cz + fdir.z * fl + sdir.z * sl,
		}
	end
	return pts
end

-- Smallest distance between two sampled perimeters (world units). Once the two
-- ovals separate this equals the edge-to-edge gap; while overlapping it stays
-- near zero, which is fine for the clamp (overlap is always a legal Leap).
local function minPerimeterGap(ptsA, ptsB)
	local best = math.huge
	for _, a in ipairs(ptsA) do
		for _, b in ipairs(ptsB) do
			local dx, dz = a.x - b.x, a.z - b.z
			local d2 = dx * dx + dz * dz
			if d2 < best then best = d2 end
		end
	end
	return math.sqrt(best)
end

-- Clamp a desired Leap centre so the base's edge stays within MAX_LEAP_INCHES of
-- the original footprint. The ghost slides along the original->pointer line: if
-- the far end is legal it's used as-is, otherwise a binary search finds the
-- furthest legal point on that line for the current (ghost) heading.
local function clampLeapPos(desired, heading)
	local dx = desired.x - leapOrig.x
	local dz = desired.z - leapOrig.z
	local dist = math.sqrt(dx * dx + dz * dz)
	if dist < 1e-6 then
		return { x = leapOrig.x, y = startY, z = leapOrig.z }
	end
	local ux, uz = dx / dist, dz / dist
	local maxGapU = toUnits(MAX_LEAP_INCHES)
	local function gapAt(d)
		local cx, cz = leapOrig.x + ux * d, leapOrig.z + uz * d
		return minPerimeterGap(leapOrigPts, ovalPerimeter(cx, cz, heading, LEAP_STEPS))
	end
	if gapAt(dist) <= maxGapU then
		return { x = desired.x, y = startY, z = desired.z }
	end
	local lo, hi = 0, dist
	for _ = 1, 24 do
		local mid = (lo + hi) * 0.5
		if gapAt(mid) <= maxGapU then lo = mid else hi = mid end
	end
	return { x = leapOrig.x + ux * lo, y = startY, z = leapOrig.z + uz * lo }
end

-- ----------------------------------------------------------------- drawing ---
local function line(a, b, color, thick)
	local ay = (a.y or curPos.y) + LINE_HEIGHT
	local by = (b.y or curPos.y) + LINE_HEIGHT
	return {
		points    = { { a.x, ay, a.z }, { b.x, by, b.z } },
		color     = color,
		thickness = thick or LINE_THICKNESS,
	}
end

-- Corridor for a straight leg: centre line + two parallel edges offset by half
-- the base width, showing the swept path of the base.
local function appendCorridor(out, a, b, heading, color)
	local side = dirFromHeading(heading + 90)
	local hw   = halfWide()
	local aL = { x = a.x + side.x * hw, y = a.y, z = a.z + side.z * hw }
	local bL = { x = b.x + side.x * hw, y = b.y, z = b.z + side.z * hw }
	local aR = { x = a.x - side.x * hw, y = a.y, z = a.z - side.z * hw }
	local bR = { x = b.x - side.x * hw, y = b.y, z = b.z - side.z * hw }
	table.insert(out, line(a, b, color))
	table.insert(out, line(aL, bL, color, LINE_THICKNESS * 0.7))
	table.insert(out, line(aR, bR, color, LINE_THICKNESS * 0.7))
end

-- Grey full-range straight guide: the swept corridor of the base over the whole
-- reachable straight distance - the two base SIDES (no centre line) plus a
-- half-oval cap of the base at EACH end (forward tip and backward tip), so you
-- can see exactly how far the base reaches either way.
local function appendRangeGuide(out, pos, heading, fwdInches, backInches, color)
	local fdir = dirFromHeading(heading)
	local side = dirFromHeading(heading + 90)
	local hw   = halfWide()
	local aL   = halfLong()
	local f    = toUnits(fwdInches)
	local b    = toUnits(backInches)
	local cf   = { x = pos.x + fdir.x * f, z = pos.z + fdir.z * f }   -- centre at max forward
	local cb   = { x = pos.x - fdir.x * b, z = pos.z - fdir.z * b }   -- centre at max backward
	local thin = LINE_THICKNESS * 0.6
	local y    = pos.y + LINE_HEIGHT
	-- Left / right swept edges (base sides).
	table.insert(out, line({ x = cb.x + side.x * hw, y = pos.y, z = cb.z + side.z * hw },
	                       { x = cf.x + side.x * hw, y = pos.y, z = cf.z + side.z * hw }, color, thin))
	table.insert(out, line({ x = cb.x - side.x * hw, y = pos.y, z = cb.z - side.z * hw },
	                       { x = cf.x - side.x * hw, y = pos.y, z = cf.z - side.z * hw }, color, thin))
	-- Half-oval cap of the base at each end (t sweeps 180deg through the tip).
	local steps = 20
	local function cap(centre, tStart)
		local pts = {}
		for i = 0, steps do
			local t  = tStart + (i / steps) * math.pi
			local fl = aL * math.cos(t)
			local sl = hw * math.sin(t)
			pts[#pts + 1] = { centre.x + fdir.x * fl + side.x * sl, y, centre.z + fdir.z * fl + side.z * sl }
		end
		table.insert(out, { points = pts, color = color, thickness = thin })
	end
	if f > 1e-3 then cap(cf, -math.pi / 2) end   -- forward half (front tip)
	if b > 1e-3 then cap(cb,  math.pi / 2) end   -- rear half (back tip)
end

-- Grey reachable cone (a "range map"): the sector the base's front tip can reach
-- by pivoting up to +/-spanDeg and then spending the remaining straight budget.
-- Drawn as an outer arc plus the two side edges from the model centre.
local function appendReachCone(out, pos, heading, spanDeg, radiusInches, color)
	local r = toUnits(radiusInches)
	local y = (pos.y or curPos.y) + LINE_HEIGHT
	local steps = 28
	local arc = {}
	for i = 0, steps do
		local h = heading - spanDeg + (2 * spanDeg) * (i / steps)
		local d = dirFromHeading(h)
		arc[#arc + 1] = { pos.x + d.x * r, y, pos.z + d.z * r }
	end
	table.insert(out, { points = arc, color = color, thickness = LINE_THICKNESS * 0.6 })
	local dL = dirFromHeading(heading - spanDeg)
	local dR = dirFromHeading(heading + spanDeg)
	table.insert(out, { points = { { pos.x, y, pos.z }, { pos.x + dL.x * r, y, pos.z + dL.z * r } }, color = color, thickness = LINE_THICKNESS * 0.6 })
	table.insert(out, { points = { { pos.x, y, pos.z }, { pos.x + dR.x * r, y, pos.z + dR.z * r } }, color = color, thickness = LINE_THICKNESS * 0.6 })
end

-- Pivot helper: a small cross drawn at the pivot anchor point. (The allowed
-- turn range is shown separately by the grey reach cone.)
local function appendPivotGuides(out, anchor, heading, y)
	local m = 0.35
	table.insert(out, line({ x = anchor.x - m, y = y, z = anchor.z }, { x = anchor.x + m, y = y, z = anchor.z }, COL_PIVOT))
	table.insert(out, line({ x = anchor.x, y = y, z = anchor.z - m }, { x = anchor.x, y = y, z = anchor.z + m }, COL_PIVOT))
end

-- Closed oval outline (the base) centred at (cx,cy,cz), long axis along heading.
local function appendGhost(out, cx, cy, cz, heading, color)
	local aLong = halfLong()
	local bWide = halfWide()
	local fdir  = dirFromHeading(heading)
	local sdir  = dirFromHeading(heading + 90)
	local pts, steps = {}, 40
	for i = 0, steps do
		local t  = (i / steps) * 2 * math.pi
		local fl = aLong * math.cos(t)
		local sl = bWide * math.sin(t)
		table.insert(pts, {
			cx + fdir.x * fl + sdir.x * sl,
			cy + LINE_HEIGHT,
			cz + fdir.z * fl + sdir.z * sl,
		})
	end
	table.insert(out, { points = pts, color = color or COL_GHOST, thickness = LINE_THICKNESS * 0.8 })

	-- Front marker: a small chevron ">" at the front edge, pointing along the
	-- heading, so the model's facing (and any rotation) is easy to read.
	local col = color or COL_GHOST
	local m   = math.max(0.18, math.min(aLong, bWide) * 0.55)
	local fex = cx + fdir.x * aLong           -- centre of the front edge
	local fez = cz + fdir.z * aLong
	local y   = cy + LINE_HEIGHT
	local apex  = { fex + fdir.x * m, y, fez + fdir.z * m }
	local barbL = { fex + sdir.x * m * 0.8, y, fez + sdir.z * m * 0.8 }
	local barbR = { fex - sdir.x * m * 0.8, y, fez - sdir.z * m * 0.8 }
	table.insert(out, { points = { barbL, apex, barbR }, color = col, thickness = LINE_THICKNESS })
end

-- Draw everything: committed legs (dim) + the active preview + the end ghost.
local function redraw(active, endPos, endHeading)
	local lines = {}
	for _, leg in ipairs(committedLegs) do
		appendCorridor(lines, leg.a, leg.b, leg.heading, COL_LEG_DONE)
	end
	for _, l in ipairs(active or {}) do table.insert(lines, l) end
	if endPos then
		appendGhost(lines, endPos.x, endPos.y or curPos.y, endPos.z, endHeading)
	end
	Global.setVectorLines(lines)
end

local function clearPreview() Global.setVectorLines({}) end

-- --------------------------------------------------------- distance readout --
-- The live distance/angle is shown as a screen-space HUD in the Global UI
-- instead of a world-space 3DText, so terrain never hides it. The Global UI is
-- SHARED (Chapter Tactics' fr_info_panel, the Move tool's HUD, etc.), so we
-- APPEND our container (id ktmove_hud) to whatever UI already exists and reuse
-- it if present -- we never clobber the rest. The Move tool builds the EXACT
-- same container, so the two tools share one HUD. Per-row updates use
-- setAttribute/setValue, which don't replace the UI.
local HUD_COLORS = { "White", "Brown", "Red", "Orange", "Yellow",
                     "Green", "Teal", "Blue", "Purple", "Pink" }

local function hudColorHex(c)
	local col = Color.fromString(c)
	if not col then return "#FFFFFF" end
	-- Lighten toward white so darker player colours stay readable via the outline.
	col = col:lerp(Color.White, 0.25)
	return "#" .. col:toHex(false)
end

local function buildHudXml()
	-- Bare outlined text per colour (no background box, so it hugs the value and
	-- can't stretch). The layout forces each text to the container width and
	-- centres it, so it always renders (a width-less Text can collapse to nothing).
	local rows = ""
	for _, c in ipairs(HUD_COLORS) do
		rows = rows .. string.format(
			'<Text id="ktmove_txt_%s" active="false" color="%s" fontSize="26" '
			.. 'fontStyle="Bold" alignment="Center" preferredHeight="32" '
			.. 'outline="#000000" outlineSize="2 -2" raycastTarget="false"> </Text>', c, hudColorHex(c))
	end
	return '<Panel id="ktmove_hud" active="true" rectAlignment="UpperCenter" '
		.. 'width="600" height="120" offsetXY="0 -80" color="#00000000" raycastTarget="false">'
		.. '<VerticalLayout childAlignment="UpperCenter" childForceExpandWidth="true" '
		.. 'childForceExpandHeight="false" spacing="2" raycastTarget="false">'
		.. rows
		.. '</VerticalLayout></Panel>'
end

-- Ensure our HUD container exists in the (possibly shared) Global UI WITHOUT
-- wiping anything else already there. Called on begin (once), not per frame.
local function ensureHud()
	local cur = ""
	pcall(function() cur = Global.UI.getXml() or "" end)
	if type(cur) ~= "string" then cur = "" end
	if cur:find("ktmove_hud", 1, true) then return end
	pcall(function() Global.UI.setXml(cur .. buildHudXml()) end)
end

local function hudShow(color, text)
	if not color then return end
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "true")
		Global.UI.setValue("ktmove_txt_" .. color, text or " ")
	end)
end

local function hudHide(color)
	if not color then return end
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "false")
		Global.UI.setValue("ktmove_txt_" .. color, " ")
	end)
end

-- Injection-safe wrappers so the begin/finish/cancel call sites read the same as
-- before but now drive the shared screen-space HUD.
local function ensureDistText()
	ensureHud()
end

local function updateDistText()
	if readoutText then
		hudShow(controlColor, readoutText)
	else
		hudHide(controlColor)
	end
end

local function destroyDistText()
	hudHide(controlColor)
end

-- ------------------------------------------------------------- update loop ---
local function s1Origin()
	if s1Mode == "pivotFront" then return "front" end
	if s1Mode == "pivotBack" then return "back" end
	return "center"
end

local function tick()
	if phase == PHASE_IDLE or not controlColor then return end
	local pointer = Player[controlColor].getPointerPosition()
	if not pointer then return end
	syncCatcher()   -- match the catch area to the current step's reach (no-op unless it changed)

	local active = {}
	local endPos, endHeading
	readoutText, readoutPos = nil, nil

	if phase == PHASE_S1 and s1Mode == "straight" then
		-- Grey full-range guide: the whole straight budget you could still spend.
		appendRangeGuide(active, curPos, curHeading, remainingInches(),
			math.max(0, MAX_BACK_INCHES - backSpent), COL_LIMIT)
		local d, e, h = straightPreview(pointer)
		prevStraight, prevEndPos, prevHeading = d, e, h
		appendCorridor(active, curPos, e, h, COL_LEG)
		endPos, endHeading = e, h
		readoutText = string.format('%.1f"', (d >= 0) and ceilToShown(d) or math.abs(d)) .. (d < 0 and " back" or "")
		readoutPos  = { x = (curPos.x + e.x) * 0.5, y = curPos.y, z = (curPos.z + e.z) * 0.5 }

	elseif phase == PHASE_S1 then
		local nh, np, anchor, delta, valid = pivotPreview(pointer, s1Origin(), curPos, curHeading)
		-- Grey reachable cones from the pivot anchor (moves with the mode): pivot
		-- +/-45, then spend the straight budget FORWARD or BACKWARD.
		local fdir = dirFromHeading(curHeading)
		local anchorFwdU = (anchor.x - curPos.x) * fdir.x + (anchor.z - curPos.z) * fdir.z
		local backRem = math.max(0, MAX_BACK_INCHES - backSpent)
		appendReachCone(active, anchor, curHeading, MAX_PIVOT_DEG,
			remainingInches() + toInches(halfLong() - anchorFwdU), COL_LIMIT)
		appendReachCone(active, anchor, curHeading + 180, MAX_PIVOT_DEG,
			backRem + toInches(halfLong() + anchorFwdU), COL_LIMIT)
		appendPivotGuides(active, anchor, curHeading, curPos.y)
		if valid then
			prevStraight, prevEndPos, prevHeading = 0, np, nh
			endPos, endHeading = np, nh
		else
			prevEndPos = nil   -- side dead zone: hide ghost, block commit
		end

	elseif phase == PHASE_PIVOT then
		local nh, np, anchor, delta, valid = pivotPreview(pointer, pivotOrigin, curPos, curHeading)
		-- Reach cones from the pivot anchor (moves with the chosen mode): forward
		-- (remaining straight budget) and backward (remaining backward budget).
		local fdir = dirFromHeading(curHeading)
		local anchorFwdU = (anchor.x - curPos.x) * fdir.x + (anchor.z - curPos.z) * fdir.z
		local backRem = math.max(0, MAX_BACK_INCHES - backSpent)
		appendReachCone(active, anchor, curHeading, MAX_PIVOT_DEG,
			remainingInches() + toInches(halfLong() - anchorFwdU), COL_LIMIT)
		appendReachCone(active, anchor, curHeading + 180, MAX_PIVOT_DEG,
			backRem + toInches(halfLong() + anchorFwdU), COL_LIMIT)
		appendPivotGuides(active, anchor, curHeading, curPos.y)
		if valid then
			prevStraight, prevEndPos, prevHeading = 0, np, nh
			endPos, endHeading = np, nh
		else
			prevEndPos = nil   -- side dead zone: hide ghost, block commit
		end

	elseif phase == PHASE_S2 then
		appendRangeGuide(active, curPos, curHeading, remainingInches(),
			math.max(0, MAX_BACK_INCHES - backSpent), COL_LIMIT)
		local d, e, h = straightPreview(pointer)
		prevStraight, prevEndPos, prevHeading = d, e, h
		appendCorridor(active, curPos, e, h, COL_LEG)
		endPos, endHeading = e, h
		readoutText = string.format('%.1f"', (d >= 0) and ceilToShown(d) or math.abs(d)) .. (d < 0 and " back" or "")
		readoutPos  = { x = (curPos.x + e.x) * 0.5, y = curPos.y, z = (curPos.z + e.z) * 0.5 }

	elseif phase == PHASE_LEAP then
		-- Rotation is STEPPED and BATCHED: handleDigit only accumulates taps into
		-- leapPendingRot; we flush the whole batch to curHeading ONCE here so any
		-- number of taps landing between two ticks all register (n taps = n steps).
		if leapPendingRot ~= 0 then
			curHeading = curHeading + leapPendingRot * LEAP_ROT_STEP
			leapPendingRot = 0
		end
		-- Here we just clamp the aimed position to the current heading and preview.
		local pos = clampLeapPos(pointer, curHeading)
		prevStraight, prevEndPos, prevHeading = 0, pos, curHeading
		-- Grey ghost = original footprint (the 1" anchor); cyan = destination.
		appendGhost(active, leapOrig.x, startY, leapOrig.z, leapOrigHeading, COL_ORIG)
		endPos, endHeading = pos, curHeading
	end

	redraw(active, endPos, endHeading)
	updateDistText()
end

local function startLoop()
	if loopHandle then return end
	loopHandle = Wait.time(tick, 1 / PREVIEW_HZ, -1)
end

local function stopLoop()
	if loopHandle then
		Wait.stop(loopHandle)
		loopHandle = nil
	end
end

-- --------------------------------------------------------- click catcher ----
-- A static transparent RECTANGLE pinned to the model, aligned to its facing and
-- sized to the area the model can actually travel THIS step: the forward budget
-- (+ margin) ahead of it and the backward budget (+ margin) behind it, only a
-- base-width-ish corridor wide. This is far smaller than the old full-envelope
-- disc, so it no longer locks a big bubble over the whole table -- it only
-- covers where the model can move. LEFT-click = apply, RIGHT-click = back.
-- Because it is a button ON the model, hovering it counts as hovering the model,
-- so the number ROW works with no binding. It is rebuilt only when the reach
-- changes (a leg commits / step-back), never per frame -- so there is no lag.

-- Remove every catcher button currently on the model (high->low: removeButton
-- reshuffles indices, so removing while iterating by index can skip one).
local function clearCatcherButtons()
	local idx = {}
	for _, b in ipairs(self.getButtons() or {}) do
		if b.click_function == "sprintCatcherClick" then idx[#idx + 1] = b.index end
	end
	table.sort(idx, function(a, b) return a > b end)
	for _, i in ipairs(idx) do self.removeButton(i) end
end

-- Forward / backward reach (inches) of the catch rectangle for a STRAIGHT step:
-- the remaining forward / backward budget + margin, each floored so a nearly-
-- spent sprint still has a clickable area.
local function catcherReach()
	local fwd  = remainingInches() + CATCHER_MARGIN_IN
	local back = math.max(0, MAX_BACK_INCHES - backSpent) + CATCHER_MARGIN_IN
	if fwd  < 3 then fwd  = 3 end
	if back < 2 then back = 2 end
	return fwd, back
end

-- Does the CURRENT step aim a PIVOT (needs the wide +/-45 front/rear swing area)
-- rather than a straight leg (narrow forward/back corridor)? True for the pivot
-- step and for step 1 when its mode is a pivot.
local function catcherIsPivot()
	if phase == PHASE_PIVOT then return true end
	if phase == PHASE_S1 and s1Mode ~= "straight" then return true end
	return false
end

-- Half-span (inches) of the centred square used while aiming a pivot: the
-- forward budget (+ margin) plus a base half-length, so the +/-45 cones and the
-- base tips all stay inside the clickable area. Floored so a spent sprint still
-- has room to click.
local function catcherPivotReach()
	local r = remainingInches() + CATCHER_MARGIN_IN + toInches(halfLong())
	return (r < 4) and 4 or r
end

-- (Re)create the catcher as a FRESH button sized to the CURRENT step:
--   * straight leg -> a NARROW rectangle aligned to the model's VISUAL facing
--     (button rotation = facingOffset), pushed forward so it runs `fwd` inches
--     ahead and `back` inches behind -- covering only the travel corridor.
--   * pivot/turn   -> a CENTRED square covering the full +/-45 swing, so you can
--     click anywhere in the front OR rear cone out to the reach.
-- The model steps/rotates to each committed leg (see applyToModel) and the button
-- rides along in local space, so it always tracks the operative's current spot and
-- facing -- no offset math. remove+recreate because editing a button does not
-- reliably rebuild its invisible click hitbox in TTS.
local function placeCatcher()
	clearCatcherButtons()
	local sc     = self.getScale()
	local uPerIn = CATCHER_UNITS_PER_IN
	if catcherIsPivot() then
		-- Centred, rotation-proof square covering the pivot swing (both cones).
		local span = 2 * catcherPivotReach() * uPerIn
		self.createButton({
			click_function = "sprintCatcherClick",
			function_owner = self,
			label          = "",
			position       = { 0, 0.6 / (sc.y ~= 0 and sc.y or 1), 0 },
			rotation       = { 0, 0, 0 },
			width          = span / (sc.x ~= 0 and sc.x or 1),
			height         = span / (sc.z ~= 0 and sc.z or 1),
			font_size      = 100,
			color          = { 0, 0, 0, 0 },
			tooltip        = catcherTooltip,
		})
		return
	end
	local fwd, back = catcherReach()
	local widthIn   = 2 * halfWide() + 2 * CATCHER_SIDE_MARGIN_IN   -- side-to-side corridor
	local depthIn   = fwd + back                                    -- front-to-back run
	local offIn     = (fwd - back) * 0.5                            -- shift forward of centre
	local fdir      = dirFromHeading(facingOffset)                  -- visual-forward in local space
	-- NB: button POSITION is in the object's local units (like the 0.6 y lift),
	-- but button WIDTH/HEIGHT use a separate UI scale (hence CATCHER_UNITS_PER_IN).
	-- So the forward shift must NOT be multiplied by uPerIn, or the hitbox flies
	-- far off the model and nothing is clickable.
	self.createButton({
		click_function = "sprintCatcherClick",
		function_owner = self,
		label          = "",
		position       = {
			(fdir.x * offIn) / (sc.x ~= 0 and sc.x or 1),
			0.6 / (sc.y ~= 0 and sc.y or 1),
			(fdir.z * offIn) / (sc.z ~= 0 and sc.z or 1),
		},
		rotation       = { 0, facingOffset, 0 },
		width          = (widthIn * uPerIn) / (sc.x ~= 0 and sc.x or 1),
		height         = (depthIn * uPerIn) / (sc.z ~= 0 and sc.z or 1),
		font_size      = 100,
		color          = { 0, 0, 0, 0 },
		tooltip        = catcherTooltip,
	})
end

local function createCatcher(tooltip)
	if catcherActive then return end
	catcherTooltip = tooltip or "Left: apply   Right: back   1/2/3/4: mode   9: finish   0: cancel"
	placeCatcher()
	catcherActive    = true
	lastCatcherKind  = catcherIsPivot()
	lastCatcherFwd, lastCatcherBack = catcherReach()
end

-- Resize/reshape the catcher for the current step. Guarded so it only rebuilds
-- when the reach OR the shape (straight corridor vs pivot swing) actually
-- changes -- e.g. a leg commits, a step-back, or switching to/from a pivot mode
-- -- never per frame, so there is no lag.
syncCatcher = function()
	if not catcherActive then return end
	local pivot     = catcherIsPivot()
	local fwd, back = catcherReach()
	if pivot == lastCatcherKind and fwd == lastCatcherFwd and back == lastCatcherBack then return end
	lastCatcherKind = pivot
	lastCatcherFwd, lastCatcherBack = fwd, back
	placeCatcher()
end

local function removeCatcher()
	if not catcherActive then return end
	clearCatcherButtons()
	catcherActive = false
end

-- ------------------------------------------------------------ history/undo ---
local function pushHistory()
	table.insert(history, {
		phase       = phase,
		pos         = { x = curPos.x, y = curPos.y, z = curPos.z },
		heading     = curHeading,
		spent       = spentInches,
		back        = backSpent,
		raw         = rawStraight,
		legs        = #committedLegs,
		s1Mode      = s1Mode,
		pivotOrigin = pivotOrigin,
	})
end

local function restoreFrom(s)
	curPos      = { x = s.pos.x, y = s.pos.y, z = s.pos.z }
	curHeading  = s.heading
	spentInches = s.spent
	backSpent   = s.back
	rawStraight = s.raw
	while #committedLegs > s.legs do table.remove(committedLegs) end
	phase        = s.phase
	s1Mode       = s.s1Mode
	pivotOrigin  = s.pivotOrigin
	-- move/rotate the model back to the restored step (it steps with each leg)
	applyToModel()
end

-- ------------------------------------------------------------ state changes --
applyToModel = function()
	local r = self.getRotation()
	self.setPosition({ curPos.x, startY, curPos.z })
	-- curHeading is the VISUAL facing; convert back to the model's transform
	-- rotation (undo the KTUI mesh offset) so the mini doesn't spin 180.
	self.setRotation({ r.x, curHeading - facingOffset, r.z })
end

local function finishSprint(pc, text)
	stopLoop()
	clearPreview()
	removeCatcher()
	destroyDistText()
	setActiveSprint(pc or controlColor, false)
	applyToModel()
	msg(pc, text or "Sprint complete.", COL_LEG)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

local function cancelSprint(pc)
	stopLoop()
	clearPreview()
	removeCatcher()
	destroyDistText()
	setActiveSprint(pc or controlColor, false)
	-- the model stepped along the sprint; put it back where it started
	if startPos then
		local r = self.getRotation()
		self.setPosition({ startPos.x, startY, startPos.z })
		self.setRotation({ r.x, (startHeading or curHeading) - facingOffset, r.z })
	end
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
	if pc then msg(pc, "Sprint cancelled.", COL_LIMIT) end
end

local function beginSprint(pc)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startY       = p.y
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	curHeading   = headingOf(fwd.x, fwd.z) + facingOffset
	startPos     = { x = p.x, z = p.z }
	startHeading = curHeading
	spentInches  = 0
	backSpent    = 0
	rawStraight  = 0
	committedLegs = {}
	history      = {}
	s1Mode       = "straight"
	pivotOrigin  = "center"
	turnOnly     = false
	phase        = PHASE_S1
	lastReport   = nil
	startLoop()
	createCatcher()
	ensureDistText()
	setActiveSprint(pc, true)
	msg(pc, "Sprint: drag to aim. 1=straight, 2/3/4=pivot front/centre/back. "
		.. "Left=apply, right=back, 9=finish straight, 0=cancel.", COL_PIVOT)
end

-- "Turn": a single pivot only (no movement). Starts straight in the pivot step;
-- 2/3/4 pick the anchor, drag to turn (+/-45deg), left-click applies & finishes.
local function beginTurn(pc)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startY       = p.y
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	curHeading   = headingOf(fwd.x, fwd.z) + facingOffset
	startPos     = { x = p.x, z = p.z }
	startHeading = curHeading
	spentInches  = 0
	backSpent    = 0
	rawStraight  = 0
	committedLegs = {}
	history      = {}
	s1Mode       = "straight"
	pivotOrigin  = "center"
	turnOnly     = true
	phase        = PHASE_PIVOT
	lastReport   = nil
	startLoop()
	createCatcher("Left: apply   Right: cancel   2/3/4: pivot point   0: cancel")
	ensureDistText()
	setActiveSprint(pc, true)
	msg(pc, "Turn: 2/3/4 = pivot from front/centre/back, drag to turn (+/-45deg). "
		.. "Left=apply, right/0=cancel.", COL_PIVOT)
end

-- "Leap" (Exodite special move): reposition the base freely by aiming, clamped
-- so any part of the base stays within 1" of any part of the original footprint,
-- with 360 rotation via STEPPED taps of 1/2 (numpad or number row), each turning
-- LEAP_ROT_STEP degrees. Left-click applies; right-click / 0 cancels.
local function beginLeap(pc)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startY       = p.y
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	curHeading   = headingOf(fwd.x, fwd.z) + facingOffset
	startPos     = { x = p.x, z = p.z }
	startHeading = curHeading
	leapOrig        = { x = p.x, z = p.z }
	leapOrigHeading = curHeading
	leapOrigPts     = ovalPerimeter(p.x, p.z, curHeading, LEAP_STEPS)
	leapPendingRot  = 0
	spentInches  = 0
	backSpent    = 0
	rawStraight  = 0
	committedLegs = {}
	history      = {}
	phase        = PHASE_LEAP
	lastReport   = nil
	startLoop()
	createCatcher("Left: apply   Right: cancel   1/2: rotate   0: cancel")
	ensureDistText()
	setActiveSprint(pc, true)
	msg(pc, 'Leap: aim to move (auto-clamped to 1").  Tap 1/2 = rotate '
		.. string.format('%d', LEAP_ROT_STEP) .. "deg.  Left=apply, right/0=cancel.", COL_PIVOT)
end

local function commitStraight(d, endPos)
	table.insert(committedLegs, {
		a = { x = curPos.x, y = curPos.y, z = curPos.z },
		b = { x = endPos.x, y = curPos.y, z = endPos.z },
		heading = curHeading,
	})
	curPos      = { x = endPos.x, y = curPos.y, z = endPos.z }
	rawStraight = rawStraight + math.abs(d)
	if d < 0 then
		backSpent = backSpent + math.abs(d)
	else
		spentInches = spentInches + math.ceil(math.abs(d) - 1e-6)
	end
	applyToModel()   -- step the model to the committed point (catcher rides centred)
end

local function commitPivot(newHeading, newPos)
	curPos     = { x = newPos.x, y = curPos.y, z = newPos.z }
	curHeading = newHeading
	applyToModel()   -- rotate/step the model to the pivot result
end

-- LEFT-click: apply the current step and advance.
local function advance(pc)
	if phase == PHASE_S1 then
		if s1Mode == "straight" then
			if not prevEndPos then return end
			pushHistory()
			local moved = math.abs(prevStraight)
			commitStraight(prevStraight, prevEndPos)
			phase       = PHASE_PIVOT
			pivotOrigin = "center"
			lastReport  = nil
			-- Callout: distance moved only (the next step is the pivot).
			msg(pc, string.format('Moved: %.1f"%s.', moved, prevStraight < 0 and " back" or ""), COL_LEG)
		else
			-- pivot-first: this pivot IS the single pivot; jump to the final
			-- leg. No callout - the pivot angle isn't useful info.
			if not prevEndPos then return end
			pushHistory()
			commitPivot(prevHeading, prevEndPos)
			phase      = PHASE_S2
			lastReport = nil
		end

	elseif phase == PHASE_PIVOT then
		-- Applying the pivot: no callout (angle isn't useful info).
		if not prevEndPos then return end
		pushHistory()
		commitPivot(prevHeading, prevEndPos)
		lastReport = nil
		if turnOnly then
			finishSprint(pc, "Turn complete.")
		elseif remainingInches() < 1 then
			finishSprint(pc, string.format('Sprint complete: %.1f" total.', rawStraight))
		else
			phase = PHASE_S2
		end

	elseif phase == PHASE_S2 then
		if prevEndPos then commitStraight(prevStraight, prevEndPos) end
		finishSprint(pc, string.format('Sprint complete: %.1f" total.', rawStraight))

	elseif phase == PHASE_LEAP then
		if prevEndPos then
			curPos     = { x = prevEndPos.x, y = curPos.y, z = prevEndPos.z }
			curHeading = prevHeading
		end
		finishSprint(pc, "Leap complete.")
	end
end

-- RIGHT-click: undo one step (or cancel from the first step).
local function stepBack(pc)
	if #history == 0 then
		cancelSprint(pc)
		return
	end
	local s = table.remove(history)
	restoreFrom(s)
	lastReport = nil
	msg(pc, "Stepped back.", COL_PIVOT)
end

-- Key 9: lock in the current step and finish. In a straight step it commits the
-- current straight move (so a short "2" and stop" needs no exact end aim). In
-- the pivot step it APPLIES the current pivot and finishes (skips the final
-- straight leg) - i.e. "apply this rotation and stop here".
local function finishStraightNoPivot(pc)
	if phase == PHASE_PIVOT then
		if prevEndPos then commitPivot(prevHeading, prevEndPos) end
		finishSprint(pc, string.format('Sprint complete: %.1f" total.', rawStraight))
		return
	end
	if phase == PHASE_S1 or phase == PHASE_S2 then
		local pointer = Player[pc] and Player[pc].getPointerPosition()
		if pointer then
			local d, e = straightPreview(pointer)
			commitStraight(d, e)
		end
		finishSprint(pc, string.format('Sprint complete: %.1f".', rawStraight))
	end
end

-- Number-key mode selection for the current step.
local function selectMode(pc, key)
	if phase == PHASE_S1 then
		if key == 1 then s1Mode = "straight"
		elseif key == 2 then s1Mode = "pivotFront"
		elseif key == 3 then s1Mode = "pivotCenter"
		elseif key == 4 then s1Mode = "pivotBack"
		else return end
		lastReport = nil
		msg(pc, "Step 1 mode: " .. s1Mode, COL_PIVOT)
	elseif phase == PHASE_PIVOT then
		if key == 2 then pivotOrigin = "front"
		elseif key == 3 then pivotOrigin = "center"
		elseif key == 4 then pivotOrigin = "back"
		else return end
		lastReport = nil
		msg(pc, "Pivot anchor: " .. pivotOrigin, COL_PIVOT)
	end
	-- PHASE_S2 is straight-only: number keys 1-4 do nothing.
end

-- Unified digit handler (0-9), shared by the numpad scripting buttons and the
-- number ROW (onNumberTyped). Returns true if it consumed the digit.
local function handleDigit(pc, digit)
	if phase == PHASE_IDLE then return false end
	if controlColor and pc ~= controlColor then return false end
	if phase == PHASE_LEAP then
		-- Deliberate single-press commands first: 9 = apply, 0 = cancel.
		if digit == 9 then advance(pc); return true
		elseif digit == 0 then cancelSprint(pc); return true end
		-- Stepped + BATCHED rotation. CRITICAL: TTS merges rapid same-key presses
		-- on the number ROW into ONE multi-digit number (three quick 1s arrive as
		-- 111, not three 1s), so an exact `digit == 1` test DROPS fast taps -- which
		-- is why they "didn't register". We DECOMPOSE the number into its digits and
		-- queue each one: every 1 = -1 step, every 2 = +1 step (11 -> two -1;
		-- 12 -> -1 then +1). The tick loop applies the summed total, so no tap is
		-- lost no matter how fast you tap.
		local matched = false
		for d in tostring(digit):gmatch("%d") do
			if d == "1" then leapPendingRot = leapPendingRot - 1; matched = true
			elseif d == "2" then leapPendingRot = leapPendingRot + 1; matched = true end
		end
		return matched
	end
	if digit >= 1 and digit <= 4 then
		selectMode(pc, digit)
	elseif digit == 9 then
		finishStraightNoPivot(pc)
	elseif digit == 0 then
		cancelSprint(pc)
	else
		return false
	end
	return true
end

-- ----------------------------------------------------------------- wiring ----

-- Invisible catcher handler. altClick == true means a right-click.
function sprintCatcherClick(_, playerColor, altClick)
	if phase == PHASE_IDLE then return end
	if controlColor and playerColor ~= controlColor then return end
	if altClick then stepBack(playerColor) else advance(playerColor) end
end

-- TTS scripting buttons = the NUMPAD by default (index 10 == the "0" key). No
-- hover needed, so this works while aiming at the table. Every digit (incl. the
-- Leap 1/2 rotate) is a discrete TAP routed straight to handleDigit -- there is
-- no held-key state, so a press always registers.
function sprintScriptingButton(index, playerColor)
	local digit = index == 10 and 0 or index
	handleDigit(playerColor, digit)
end

-- Release handler kept as a harmless no-op: the numpad rotate keys are now
-- stepped taps (see sprintScriptingButton), so nothing needs to happen on key-up.
function sprintScriptingButtonUp(index, playerColor)
end

-- Hotkey entry points, called on the HOVERED model by the global hotkeys in
-- setupSprintTool. Each begins its action only when idle. Mirrors the Move/Dash
-- hotkeys in move-tool.lua.
function sprintHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginSprint((params or {}).color) end
end
function turnHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginTurn((params or {}).color) end
end
function leapHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginLeap((params or {}).color) end
end

-- Named-hotkey entry points on the model for the in-action controls (mode /
-- rotate / finish / cancel). They mirror the number-row / numpad inputs but as
-- rebindable game keys, and are phase-guarded so each only fires when its step
-- is live: mode keys during a Sprint/Turn step, rotate keys during a Leap.
function sprintKeyMode(params)
	local p = params or {}
	if phase == PHASE_IDLE or phase == PHASE_LEAP then return end
	if controlColor and p.color and p.color ~= controlColor then return end
	selectMode(p.color, p.key)
end

function sprintKeyRotate(params)
	local p = params or {}
	if phase ~= PHASE_LEAP then return end
	if controlColor and p.color and p.color ~= controlColor then return end
	leapPendingRot = leapPendingRot + (p.dir or 0)
end

function sprintKeyFinish(params)
	handleDigit((params or {}).color, 9)
end

function sprintKeyCancel(params)
	handleDigit((params or {}).color, 0)
end

-- Resolve the model a player is currently sprinting: prefer the active-sprint
-- registry (works even when the cursor is aimed away, past the catcher), fall
-- back to the hovered object. Then call fn on it with { color = ..., ...extra }.
local function sprintKeyDispatch(color, hovered, fn, extra)
	local obj = nil
	local guid = Global.getVar("KT_SPRINT_ACTIVE_" .. color)
	if type(guid) == "string" and guid ~= "" then obj = getObjectFromGUID(guid) end
	if obj == nil and hovered ~= nil and hovered.call ~= nil then obj = hovered end
	if obj == nil or obj.call == nil then return end
	local params = { color = color }
	if extra then for k, v in pairs(extra) do params[k] = v end end
	obj.call(fn, params)
end

-- Registers the context-menu items plus optional keyboard shortcuts. Advancing/
-- cancelling happen via clicks and number keys, so only the entry points live in
-- the menu.
function setupSprintTool()
	self.addContextMenuItem("Sprint", function(pc)
		if phase == PHASE_IDLE then beginSprint(pc) end
	end, false)
	self.addContextMenuItem("Turn", function(pc)
		if phase == PHASE_IDLE then beginTurn(pc) end
	end, false)
	self.addContextMenuItem("Leap", function(pc)
		if phase == PHASE_IDLE then beginLeap(pc) end
	end, false)
	-- Optional keyboard shortcuts. Registered ONCE globally (guarded via Global
	-- vars) so they aren't re-registered by every model; each callback starts the
	-- action on whatever model the player is HOVERING. Bind keys under
	-- Options -> Controls -> Game Keys ("KT: Sprint/Turn/Leap (hovered model)").
	-- Sprint/Turn/Leap only exist on MOUNTED operatives, so these keys only act on
	-- models that carry this tool.
	if Global.getVar("KT_SPRINT_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_HOTKEY", true)
		addHotkey("KT: Sprint (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("sprintHotkeyTrigger", { color = color })
			end
		end, false)
	end
	if Global.getVar("KT_TURN_HOTKEY") ~= true then
		Global.setVar("KT_TURN_HOTKEY", true)
		addHotkey("KT: Turn (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("turnHotkeyTrigger", { color = color })
			end
		end, false)
	end
	if Global.getVar("KT_LEAP_HOTKEY") ~= true then
		Global.setVar("KT_LEAP_HOTKEY", true)
		addHotkey("KT: Leap (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("leapHotkeyTrigger", { color = color })
			end
		end, false)
	end
	-- In-action controls as rebindable game keys (mode / rotate / finish / cancel),
	-- routed to the ACTIVE sprint model via the registry so they work while the
	-- cursor is aimed at the table. Bind under Options -> Controls -> Game Keys.
	if Global.getVar("KT_SPRINT_MODE1_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_MODE1_HOTKEY", true)
		addHotkey("KT: Sprint/Turn straight (mode 1)", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyMode", { key = 1 })
		end, false)
	end
	if Global.getVar("KT_SPRINT_MODE2_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_MODE2_HOTKEY", true)
		addHotkey("KT: Sprint/Turn pivot from front (mode 2)", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyMode", { key = 2 })
		end, false)
	end
	if Global.getVar("KT_SPRINT_MODE3_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_MODE3_HOTKEY", true)
		addHotkey("KT: Sprint/Turn pivot from centre (mode 3)", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyMode", { key = 3 })
		end, false)
	end
	if Global.getVar("KT_SPRINT_MODE4_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_MODE4_HOTKEY", true)
		addHotkey("KT: Sprint/Turn pivot from back (mode 4)", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyMode", { key = 4 })
		end, false)
	end
	if Global.getVar("KT_LEAP_ROTL_HOTKEY") ~= true then
		Global.setVar("KT_LEAP_ROTL_HOTKEY", true)
		addHotkey("KT: Leap rotate left", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyRotate", { dir = -1 })
		end, false)
	end
	if Global.getVar("KT_LEAP_ROTR_HOTKEY") ~= true then
		Global.setVar("KT_LEAP_ROTR_HOTKEY", true)
		addHotkey("KT: Leap rotate right", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyRotate", { dir = 1 })
		end, false)
	end
	if Global.getVar("KT_SPRINT_FINISH_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_FINISH_HOTKEY", true)
		addHotkey("KT: Sprint finish", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyFinish")
		end, false)
	end
	if Global.getVar("KT_SPRINT_CANCEL_HOTKEY") ~= true then
		Global.setVar("KT_SPRINT_CANCEL_HOTKEY", true)
		addHotkey("KT: Sprint cancel", function(color, hovered)
			sprintKeyDispatch(color, hovered, "sprintKeyCancel")
		end, false)
	end
end

-- A quiet teardown for when the player physically PICKS UP the model mid-sprint:
-- stop the preview, drop the HUD/catcher, but DON'T snap the model back and
-- DON'T broadcast a "cancelled" message -- the pickup is a deliberate manual
-- reposition, not a cancel, so it shouldn't give false "Sprint cancelled" feedback.
local function abortSprint()
	stopLoop()
	clearPreview()
	removeCatcher()
	destroyDistText()
	setActiveSprint(controlColor, false)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

-- A manual pickup is NOT a cancel: tear down the preview/HUD/catcher quietly and
-- leave the model where the player drops it (no snap-back, no callout).
function sprintOnPickUp(playerColor)
	if phase ~= PHASE_IDLE then abortSprint() end
end

-- onLoad / onPickUp / onScriptingButtonDown are CHAINED: any pre-existing
-- handler runs first, then ours. Standalone the previous handler is nil, so
-- only ours runs. Appended onto a host model (e.g. a KTUI mini) the host's
-- handlers still run, so nothing is lost. This is why the tool is injection-safe.
local _sprint_prev_onLoad = onLoad
function onLoad(...)
	-- pcall-guard the host's onLoad: a broken host extender (e.g. a third-party
	-- KTUI / Command Node extender that errors inside its own refreshUI) must not
	-- abort loading and drop the Sprint tool. Our setup always runs; the host keeps
	-- whatever it managed to complete before the error.
	if _sprint_prev_onLoad then pcall(_sprint_prev_onLoad, ...) end
	setupSprintTool()
end

local _sprint_prev_onPickUp = onPickUp
function onPickUp(...)
	if _sprint_prev_onPickUp then _sprint_prev_onPickUp(...) end
	sprintOnPickUp(...)
end

local _sprint_prev_onScriptingButtonDown = onScriptingButtonDown
function onScriptingButtonDown(...)
	if _sprint_prev_onScriptingButtonDown then _sprint_prev_onScriptingButtonDown(...) end
	sprintScriptingButton(...)
end

local _sprint_prev_onScriptingButtonUp = onScriptingButtonUp
function onScriptingButtonUp(...)
	if _sprint_prev_onScriptingButtonUp then _sprint_prev_onScriptingButtonUp(...) end
	sprintScriptingButtonUp(...)
end

-- Number ROW typed while hovering the model (no binding needed). The catcher is
-- a transparent button pinned to the model sized to the reach, so hovering
-- anywhere in it counts as hovering the model and the number ROW works across
-- the whole reach. We consume the row here and return true so the host's default
-- (e.g. setting wounds) is suppressed; when idle we defer to the host.
local _sprint_prev_onNumberTyped = onNumberTyped
function onNumberTyped(playerColor, number, alt)
	if phase ~= PHASE_IDLE and (not controlColor or playerColor == controlColor) then
		handleDigit(playerColor, number)
		return true
	end
	if _sprint_prev_onNumberTyped then return _sprint_prev_onNumberTyped(playerColor, number, alt) end
end
]=]

-- kt-datacards: Load Stats to Model
-- Card stores operative data in GMNotes (JSON).
-- Context menu "Load stats" finds a KTUIMini on top,
-- shows a weapon selection popup (if multiple weapons),
-- compares current vs new, reports diffs, and applies changes.

-- Persistent state for selection flow
local pendingData = nil
local pendingModel = nil
local pendingPlayerColor = nil
local selectionData = nil
local groupSelections = {}
local exclusiveSets = {}
local activeSet = 1

-- Faction-rule "Choose upgrades" flow. Mounted operatives pick N of the
-- <archetype> UPGRADE options embedded in GMNotes.upgrades = {select, options}.
local upgradeOptions = nil
local upgradeChosen = {}
local upgradeSelect = 2
local upgradeModel = nil
local upgradeData = nil
local upgradePlayerColor = nil

-- Context menu order (TTS shows items top -> bottom in REGISTRATION order):
--   1. Update card        reserved top slot (self-update lives in the updater
--                          tools; not wired here yet -- see TODO).
--   2. Load everything    one button: stats (+loadout) -> faction upgrades ->
--                          operative counters -> movement. Excludes Rotate base.
--   3. Load stats          stats + weapons; ALWAYS forces the loadout popup when present.
--   4. Movement           Move (non-mounted) or Sprint/Turn/Leap (mounted).
--   5. Faction specifics   e.g. Choose upgrades (chapter tactics / gore tank / counters).
--   6. Special            low-frequency extras (Rotate base 90), always last.
function onLoad()
    -- 1. TODO: "Update card" self-update item belongs here, at the very top.

    -- 2. One-button setup: stats + loadout + faction rules + movement.
    self.addContextMenuItem("Load everything", loadEverything)

    -- 3. Stats only. Always prompts the loadout selection when the operative has
    --    one (there is no silent "apply all" anymore).
    self.addContextMenuItem("Load stats", loadStatsToModel)

    -- 4. Movement action for the model on top (keyword-gated by embedded code).
    if type(SPRINT_TOOL_CODE) == "string" and hasKeyword("MOUNTED") then
        self.addContextMenuItem("Add sprint action", addSprintAction)
    end
    if type(MOVE_TOOL_CODE) == "string" and not hasKeyword("MOUNTED") then
        self.addContextMenuItem("Add Move Action", addMoveAction)
    end

    -- 5. Faction specifics.
    if hasUpgrades() then
        self.addContextMenuItem("Choose upgrades", chooseUpgrades)
    end

    -- 6. Special (always last).
    if hasOvalBase() then
        self.addContextMenuItem("Special: Rotate base 90", rotateBase90)
    end
end

-- helpers

-- Object types we accept as a "model" that can receive stats. Any of these can
-- be turned into a KTUI extender mini on the fly.
local MODEL_TYPES = {
    Custom_Model      = true,
    Figurine_Custom   = true,
    Custom_Assetbundle= true,
    Figurine          = true,
}

function isModelLike(obj)
    return obj ~= nil and MODEL_TYPES[obj.type] == true
end

function findModelOnCard()
    local pos = self.getPosition()
    local hits = Physics.cast({
        origin       = Vector(pos.x, pos.y + 1.5, pos.z),
        direction    = {0, -1, 0},
        type         = 2,
        size         = {2, 2, 2},
        max_distance = 3,
    })
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.hasTag("KTUIMini") then return obj end
    end
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and isModelLike(obj) then return obj end
    end
    return nil
end

function trunc(s, n)
    if s == nil then return "" end
    s = tostring(s)
    if #s <= n then return s end
    return s:sub(1, n) .. "..."
end

function valEq(a, b)
    return tostring(a) == tostring(b)
end

-- Parse a base-size stat into (x, z) millimetres. Round bases are a single
-- number (e.g. 32 -> 32,32); oval bases are "AxB" (e.g. "75x42" -> 75,42). The
-- KTUI extender draws base.x and base.z independently, so an oval base ring/mesh
-- falls out for free once the two dimensions are split. Returns nil,nil on junk.
function parseBaseSize(raw)
    if type(raw) == "number" then
        return raw, raw
    end
    if type(raw) == "string" then
        local a, b = string.match(raw, "^%s*(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)%s*$")
        if a and b then
            return tonumber(a), tonumber(b)
        end
        local n = tonumber(raw)
        if n then return n, n end
    end
    return nil, nil
end

function tableEq(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return valEq(a, b) end
    if #a ~= #b then return false end
    for i = 1, #a do
        if not tableEq(a[i], b[i]) then return false end
    end
    for k, v in pairs(a) do
        if not tableEq(v, b[k]) then return false end
    end
    for k, v in pairs(b) do
        if a[k] == nil then return false end
    end
    return true
end

function rebuildDescription(data)
    local lines = {}
    table.insert(lines, string.format(
        "[D36B3E][[84E680]APL[-] [ffffff]%s[-]] [[84E680]MOVE[-] [ffffff]%s\"[-]]",
        tostring(data.stats.APL), tostring(data.stats.Move)))
    table.insert(lines, string.format(
        "[[84E680]SAVE[-] [ffffff]%s+[-]] [[84E680]WOUNDS[-] [ffffff]%s[-]][-]",
        tostring(data.stats.Save), tostring(data.stats.Wounds)))
    if data.keywords then
        table.insert(lines, "[C5C5C5]" .. table.concat(data.keywords, ", ") .. "[-]")
    end
    table.insert(lines, "[31B32B]Weapons[-]")
    if data.weapons then
        for _, w in ipairs(data.weapons) do
            table.insert(lines, w.name or "?")
            local s = w.stats or {}
            table.insert(lines, string.format("[84E680]ATK[-] %s [84E680]HIT[-] %s [84E680]DMG[-] %s",
                s.ATK or "?", s.HIT or "?", s.DMG or "?"))
            if s.WR and s.WR ~= "" then
                table.insert(lines, "[84E680]WR[-]: " .. s.WR)
            end
            table.insert(lines, "")
        end
    end
    if data.abilities and #data.abilities > 0 then
        table.insert(lines, "---")
        table.insert(lines, "[31B32B]Abilities[-]")
        for _, ab in ipairs(data.abilities) do
            table.insert(lines, "- [EF8450]" .. (ab.name or "?") .. "[-]")
        end
    end
    if data.actions and #data.actions > 0 then
        table.insert(lines, "[31B32B]Actions[-]")
        for _, ac in ipairs(data.actions) do
            table.insert(lines, "- [D46D6C]" .. (ac.name or "?") .. "[-]")
        end
    end
    return table.concat(lines, "\n")
end

-- weapon selection popup

function findSetForGroup(g)
    for s, set in ipairs(exclusiveSets) do
        for _, sg in ipairs(set) do
            if sg == g then return s end
        end
    end
    return 1
end

function isGroupInActiveSet(g)
    if #exclusiveSets == 0 then return true end
    for _, sg in ipairs(exclusiveSets[activeSet] or {}) do
        if sg == g then return true end
    end
    return false
end

function buildSelectionPanelXml(selection)
    local rows = ""
    local totalOptions = 0
    local orDividers = 0

    -- Track which groups start a new exclusive set (for OR dividers)
    local setStartGroups = {}
    if #exclusiveSets > 1 then
        for s = 2, #exclusiveSets do
            local firstGroup = exclusiveSets[s][1]
            setStartGroups[firstGroup] = true
        end
    end

    for g, group in ipairs(selection.groups) do
        local inActive = isGroupInActiveSet(g)

        -- OR divider between exclusive sets
        if setStartGroups[g] then
            rows = rows .. '<Text id="or_div" fontSize="10" fontStyle="Bold" color="#FF6600" '
                .. 'preferredHeight="20" alignment="MiddleCenter">---- OR ----</Text>\n'
            orDividers = orDividers + 1
        elseif g > 1 then
            rows = rows .. '<Image color="rgba(255,255,255,0.15)" preferredHeight="1" />\n'
        end
        if #selection.groups > 1 then
            local headerColor = inActive and "#AAAAAA" or "#555555"
            rows = rows .. string.format(
                '<Text id="hdr_%d" fontSize="10" fontStyle="Bold" color="%s" '
                .. 'preferredHeight="18" alignment="MiddleLeft">Choose one:</Text>\n',
                g, headerColor)
        end
        for o, option in ipairs(group) do
            local isOn = (inActive and o == 1) and "true" or "false"
            local textColor = inActive and "#FFFFFF" or "#666666"
            local label = option.label or ("Option " .. o)
            -- Swap the "; " separator to " + " BEFORE XML-escaping. If escaping runs
            -- first, an escaped entity like "&amp; " contains "; " and the separator
            -- pass mangles it into "&amp + ", breaking the entity and the whole panel
            -- XML (e.g. loadouts such as "dominator maul & assault shield").
            label = label:gsub("; ", " + ")
            label = label:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")

            rows = rows .. string.format(
                '<Toggle id="sel_%d_%d" isOn="%s" '
                .. 'onValueChanged="onSelectionToggle" '
                .. 'fontSize="10" textColor="%s" colors="#444444|#666666|#333333|#222222" '
                .. 'toggleWidth="16" toggleHeight="16">'
                .. '%s</Toggle>\n',
                g, o, isOn, textColor, label
            )
            totalOptions = totalOptions + 1
        end
    end

    local headerText = #selection.groups > 1 and "Select Loadout" or "Select Weapon"

    return string.format([[
<Panel id="selectionPanel" active="true"
       width="224" height="%d"
       color="rgba(0,0,0,0.92)"
       padding="6 6 6 6"
       position="0 0 -50"
       rotation="0 0 180"
       allowDragging="true">
  <VerticalLayout spacing="2" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900"
          alignment="MiddleCenter" preferredHeight="20">%s</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="btnApply" onClick="onApplySelection"
              fontSize="10" fontStyle="Bold"
              colors="#2E7D32|#388E3C|#1B5E20|#555555"
              textColor="#FFFFFF">Apply</Button>
      <Button id="btnCancel" onClick="onCancelSelection"
              fontSize="10"
              colors="#C62828|#D32F2F|#B71C1C|#555555"
              textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], 64 + totalOptions * 22 + #selection.groups * 20 + orDividers * 22, headerText, rows)
end

function onSelectionToggle(player, value, id)
    local g, o = id:match("sel_(%d+)_(%d+)")
    g, o = tonumber(g), tonumber(o)
    if not g or not o then return end

    -- Handle exclusive set switching
    if #exclusiveSets > 1 and value == "True" then
        local clickedSet = findSetForGroup(g)
        if clickedSet ~= activeSet then
            activeSet = clickedSet
            -- Deselect and dim toggles in other sets; brighten active set
            for s, set in ipairs(exclusiveSets) do
                if s ~= activeSet then
                    for _, sg in ipairs(set) do
                        groupSelections[sg] = nil
                        self.UI.setAttribute("hdr_" .. sg, "color", "#555555")
                        for i = 1, #selectionData.groups[sg] do
                            self.UI.setAttribute("sel_" .. sg .. "_" .. i, "isOn", "false")
                            self.UI.setAttribute("sel_" .. sg .. "_" .. i, "textColor", "#666666")
                        end
                    end
                else
                    for _, sg in ipairs(set) do
                        self.UI.setAttribute("hdr_" .. sg, "color", "#AAAAAA")
                        for i = 1, #selectionData.groups[sg] do
                            self.UI.setAttribute("sel_" .. sg .. "_" .. i, "textColor", "#FFFFFF")
                        end
                        if not groupSelections[sg] and sg ~= g then
                            groupSelections[sg] = 1
                            self.UI.setAttribute("sel_" .. sg .. "_1", "isOn", "true")
                        end
                    end
                end
            end
        end
    end

    if value == "True" then
        groupSelections[g] = o
        -- Radio behavior: turn off other options in same group
        if selectionData and selectionData.groups and selectionData.groups[g] then
            for i = 1, #selectionData.groups[g] do
                if i ~= o then
                    self.UI.setAttribute("sel_" .. g .. "_" .. i, "isOn", "false")
                end
            end
        end
    else
        -- Prevent deselecting the current selection (radio: always one selected)
        if groupSelections[g] == o then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onApplySelection(player, value, id)
    self.UI.setXml("")
    if not pendingData or not pendingModel or not selectionData then return end

    -- Collect weapon indices from selections + fixed weapons
    local weaponSet = {}

    if selectionData.fixed then
        for _, idx in ipairs(selectionData.fixed) do
            weaponSet[idx + 1] = true  -- Convert 0-based to Lua 1-based
        end
    end

    -- Determine which groups to include (active set only, or all if no exclusive sets)
    local activeGroups = {}
    if #exclusiveSets > 0 then
        for _, g in ipairs(exclusiveSets[activeSet] or {}) do
            activeGroups[g] = true
        end
    else
        for g = 1, #selectionData.groups do
            activeGroups[g] = true
        end
    end

    for g, group in ipairs(selectionData.groups) do
        if activeGroups[g] then
            local sel = groupSelections[g] or 1
            local option = group[sel]
            if option and option.weapons then
                for _, idx in ipairs(option.weapons) do
                    weaponSet[idx + 1] = true
                end
            end
        end
    end

    -- Filter weapons to selected set
    local selectedWeapons = {}
    for i, w in ipairs(pendingData.weapons) do
        if weaponSet[i] then
            table.insert(selectedWeapons, w)
        end
    end
    pendingData.weapons = selectedWeapons

    -- Rebuild description with filtered weapons
    pendingData.description = rebuildDescription(pendingData)

    local changes = diffAndApply(pendingModel, pendingData, pendingPlayerColor)

    if #changes == 0 then
        broadcastToColor("Already up to date.", pendingPlayerColor, Color.White)
    elseif #changes == 1 then
        broadcastToColor("Updated: " .. changes[1], pendingPlayerColor, Color.Green)
    else
        local msg = "Updated:\n"
        for _, c in ipairs(changes) do
            msg = msg .. " - " .. c .. "\n"
        end
        broadcastToColor(msg, pendingPlayerColor, Color.Green)
    end

    local pc = pendingPlayerColor
    pendingData = nil
    pendingModel = nil
    pendingPlayerColor = nil
    selectionData = nil
    -- Advance the "Load everything" chain (no-op unless active).
    if loadEverythingActive then afterStatsLoaded(pc) end
end

function onCancelSelection(player, value, id)
    self.UI.setXml("")
    cancelLoadEverything()
    broadcastToColor("Selection cancelled.", pendingPlayerColor or player.color, Color.White)
    pendingData = nil
    pendingModel = nil
    pendingPlayerColor = nil
    selectionData = nil
end

-- diff and apply

-- Backfill the minimal state that the KTUI extender model script expects so a
-- plain model becomes KTUI-compatible after loading stats. This only fills
-- missing fields, so it never overwrites an existing extender mini's data.
-- Only the bare basics needed by the extender (onLoad / refreshUI /
-- refreshVectors) are set here -- not the full Command Node feature set.
function ensureKtuiState(ms, data)
    ms.stats = ms.stats or {}
    ms.info  = ms.info or {}
    ms.info.categories = ms.info.categories or {}
    ms.info.weapons    = ms.info.weapons or {}
    ms.info.special    = ms.info.special or {}
    ms.info.psychic    = ms.info.psychic or {}
    ms.info.abilities  = ms.info.abilities or {}
    ms.info.actions    = ms.info.actions or {}
    ms.info.upgrades   = ms.info.upgrades or {}
    if ms.roles         == nil then ms.roles = {} end
    if ms.hiddenRoles   == nil then ms.hiddenRoles = {} end
    if ms.items         == nil then ms.items = {} end
    if ms.attachments   == nil then ms.attachments = {} end
    if ms.holding       == nil then ms.holding = false end
    -- uiHeight/uiAngle are read unguarded by the real KT UI extender's refreshUI
    -- (e.g. `"0 0 -"..tostring(state.uiHeight*100)`). A nil or non-number here is
    -- the classic "attempt to concatenate a nil value at refreshUI" crash, so we
    -- force them to valid numbers on every apply -- never leave them as-is.
    if type(ms.uiHeight) ~= "number" or ms.uiHeight <= 0 then ms.uiHeight = 2 end
    if type(ms.uiAngle)  ~= "number" then ms.uiAngle = 0 end
    -- getUIPosition() returns nil for an out-of-range index -> the same refreshUI
    -- concat crash when the in-place refresh runs without onLoad's default.
    if type(ms.uiPositionIndex) ~= "number" then ms.uiPositionIndex = 1 end
    if ms.display_arrows == nil then ms.display_arrows = false end
    if ms.base          == nil then
        local bx, bz = parseBaseSize(data.stats and data.stats.Base)
        ms.base = { x = bx or 25, z = bz or 25 }
    end
    if ms.modelid == nil or ms.modelid == "" then
        local slug = tostring(data.name or "operative"):lower():gsub("[^%w]+", "-")
        slug = slug:gsub("^%-+", ""):gsub("%-+$", "")
        if slug == "" then slug = "operative" end
        ms.modelid = "ktui-" .. slug
    end
    -- owner is assigned in diffAndApply (baked into script_state) so the table
    -- Save/Load Positions + Ready Operatives can find the model.
end

function diffAndApply(model, data, playerColor, replaceScript, modelScript)
    local changes = {}

    local msRaw = model.script_state
    local ms = {}
    if msRaw and msRaw ~= "" then
        local ok, parsed = pcall(function() return JSON.decode(msRaw) end)
        if ok and parsed then ms = parsed end
    end

    -- What kind of model is this?
    --  * isKtui    : already a KTUI mini of ANY kind (our bundled one OR the real
    --                KT UI extender). Card loading preserves its script; the
    --                command node explicitly opts into replacement.
    --  * isManaged : specifically OUR bundled mini (we tag those "KTUIMiniDatacard").
    --                Only our own mini is safe to hard-reload() as a fallback,
    --                because its onLoad tolerates a missing owner.
    -- A truly plain model (neither tag) gets our bundled script installed.
    local isKtui    = model.hasTag("KTUIMini")
    local isManaged = model.hasTag("KTUIMiniDatacard")
    -- Our OWN managed mini carrying an older script version -> re-stamp (upgrade),
    -- mirroring how the real extender re-applies its latest. Real extender minis
    -- (KTUIMini but NOT managed) are never re-stamped -- only their state updates.
    local ktuiOutdated = false
    if isManaged and type(KTUI_MODELSCRIPT_VERSION) == "string" then
        local modelVer
        pcall(function() modelVer = model.getVar("KT_MODELSCRIPT_VERSION") end)
        ktuiOutdated = modelVer ~= KTUI_MODELSCRIPT_VERSION
    end

    ms.stats = ms.stats or {}
    ms.info  = ms.info or {}

    ensureKtuiState(ms, data)

    -- 1. Core stats
    local oldMaxWounds = ms.stats["Wounds"]
    local statMap = {
        { key = "APL",    src = data.stats.APL    },
        { key = "Move",   src = data.stats.Move   },
        { key = "Save",   src = data.stats.Save   },
        { key = "Wounds", src = data.stats.Wounds },
    }
    for _, s in ipairs(statMap) do
        local old = ms.stats[s.key]
        local new = s.src
        if not valEq(old, new) then
            table.insert(changes, string.format("%s: %s -> %s", s.key, tostring(old or "-"), tostring(new)))
            ms.stats[s.key] = new
        end
    end

    -- Base size: physical base diameter (mm) used for the extender's base ring.
    -- Update it on every apply so swapping operatives resizes the ring.
    if data.stats and data.stats.Base ~= nil then
        local bx, bz = parseBaseSize(data.stats.Base)
        if bx then
            local function baseStr(x, z)
                if x == nil then return "-" end
                if valEq(x, z) then return tostring(x) end
                return string.format("%sx%s", tostring(x), tostring(z))
            end
            -- Store the long dimension on Z (front-back). "Rotate base 90" can
            -- later swap x/z to put the long axis left-right instead. Round bases
            -- (bx==bz) are orientation-independent.
            if not valEq(bx, bz) then
                bx, bz = math.min(bx, bz), math.max(bx, bz)
            end
            local oldX = (type(ms.base) == "table") and tonumber(ms.base.x) or nil
            local oldZ = (type(ms.base) == "table") and tonumber(ms.base.z) or nil
            local oldStr, newStr = baseStr(oldX, oldZ), baseStr(bx, bz)
            if oldStr ~= newStr then
                table.insert(changes, string.format("Base: %smm -> %smm", oldStr, newStr))
            end
            ms.base = { x = bx, z = bz }
            ms.stats.Base = data.stats.Base
        end
    end

    -- Always reset wounds to full when loading stats
    if data.stats.Wounds then
        ms.wounds = data.stats.Wounds
        -- The real KT UI extender reads MAX wounds from the abbreviated key
        -- `state.stats.W` (not `Wounds`). Keep it in sync so switching operatives
        -- updates the fancy wound bar instead of showing the previous op's max.
        ms.stats.W = data.stats.Wounds
    end

    -- 2. Name
    if data.name and ms.info.name ~= data.name then
        table.insert(changes, string.format("Name: %s -> %s", trunc(ms.info.name, 30), data.name))
        ms.info.name = data.name
        ms.info.modelType = data.name
    end

    -- 3. Keywords
    if data.keywords and not tableEq(ms.info.categories, data.keywords) then
        table.insert(changes, "Keywords updated")
        ms.info.categories = data.keywords
    end

    -- 4. Weapons (always clear and replace)
    if data.weapons then
        local weaponNames = {}
        for _, w in ipairs(data.weapons) do
            table.insert(weaponNames, w.plain_name or "?")
        end
        table.insert(changes, string.format("Weapons: %s", table.concat(weaponNames, ", ")))

        ms.info.weapons = data.weapons

        local ups = {}
        for _, w in ipairs(data.weapons) do
            table.insert(ups, w.plain_name or w.name)
        end
        ms.info.upgrades = ups

        if data.weapon_rules then
            ms.info.rules = data.weapon_rules
        else
            ms.info.rules = {}
        end
    end

    -- 5. Abilities
    if data.abilities then
        local oldA = ms.info.abilities or {}
        if not tableEq(oldA, data.abilities) then
            for _, ab in ipairs(data.abilities) do
                table.insert(changes, string.format("Ability: %s", ab.name or "?"))
            end
            ms.info.abilities = data.abilities
        end
    end

    -- 6. Actions
    if data.actions then
        local oldAc = ms.info.actions or {}
        if not tableEq(oldAc, data.actions) then
            for _, ac in ipairs(data.actions) do
                table.insert(changes, string.format("Action: %s", ac.name or "?"))
            end
            ms.info.actions = data.actions
        end
    end

    -- 7. Description
    if data.description then
        local oldDesc = model.getDescription()
        if oldDesc ~= data.description then
            model.setDescription(data.description)
            if #changes == 0 then
                table.insert(changes, "Description updated")
            end
        end
    end

    -- 8. Nickname (order + wounds + name)
    if data.stats and data.stats.Wounds then
        local w = data.stats.Wounds
        local cur = model.getName()
        local wStr = string.format("{%d/%d}", w, w)
        -- Extract order prefix (e.g. "[FF5500]E[-] ") if present
        local prefix = cur:match("^(%[%x+%].-%[%-%]%s*)") or ""
        cur = prefix .. wStr .. " " .. (data.name or cur)
        model.setName(cur)
    end

    -- Write back
    -- A plain model (no KTUI tag) OR our OWN managed mini on an OLD version gets
    -- the current composed script (re)installed. Command-node replacement also
    -- reinstalls current scripts and real extender minis; ordinary card loading
    -- preserves real extender scripts and refreshes their state in place.
    -- playerColor (optional) is used to assign the KTUI owner on a (re)stamp.
    local installedScript = modelScript or KTUI_MODELSCRIPT
    local needsScript = (replaceScript or (not isKtui) or ktuiOutdated) and installedScript ~= nil and installedScript ~= ""
    if #changes > 0 or needsScript then
        -- Bake the KTUI owner into the persisted state (never a post-reload call).
        -- The table-level Save/Load Positions + Ready Operatives SKIP any model whose
        -- getOwningPlayer() is nil, so state.owner must be a seated player's steam_id
        -- AND must survive every reload in the chain. Keep an existing owner, else
        -- assign the loader; loadState restores it, so it persists (no race).
        if not ms.owner or ms.owner == "" then
            local prev
            if isKtui then pcall(function() prev = model.call("getOwningPlayer") end) end
            if prev and prev.steam_id and prev.steam_id ~= "" then
                ms.owner = prev.steam_id
            elseif playerColor and Player[playerColor] and Player[playerColor].steam_id ~= "" then
                ms.owner = Player[playerColor].steam_id
            end
        end
        model.script_state = JSON.encode(ms)
        if needsScript then
            -- Install (plain model) or upgrade (our managed mini on an old version)
            -- the composed KTUI script + tags, then reload. State (owner/wounds) is
            -- preserved via the script_state we just wrote.
            model.setLuaScript(installedScript)
            if not model.hasTag("KTUIMini") then model.addTag("KTUIMini") end
            model.addTag("KTUIMiniDatacard")
            table.insert(changes, replaceScript and "Installed command-node model script"
                or (ktuiOutdated and "Upgraded KTUI script" or "Prepared model for KTUI extender"))
            model.reload()
        else
            -- Already a KTUI mini (ours OR the real extender): refresh in place so
            -- the existing script/UI is preserved.
            --
            -- First heal the real extender's malformed getWoundPanelWidth (see
            -- healExtenderScript). If we detect it, patch this model's OWN copy of
            -- the script (never the extender object) and reload so the corrected
            -- chunk re-parses; onLoad rebuilds the fancy UI from the script_state we
            -- just wrote. This is what makes repeat loads consistent.
            local healed, didHeal = healExtenderScript(model.getLuaScript() or "")
            if didHeal then
                model.setLuaScript(healed)
                pcall(function() model.reload() end)
                table.insert(changes, "Patched extender UI script")
            else
                -- Redraw the base ring (refreshVectors) AND the status UI
                -- (refreshUI). Each is guarded so one failure can't halt the apply.
                -- Fall back to a full reload() only if the in-place refresh throws;
                -- reload re-runs the extender's onLoad -> loadState, which re-reads
                -- the valid script_state we just wrote (uiHeight etc. guaranteed
                -- present), rebuilding the fancy UI cleanly.
                local ok = pcall(function()
                    model.call("loadState")
                    pcall(function() model.call("refreshVectors") end)
                    model.call("refreshUI")
                end)
                if not ok then
                    pcall(function() model.reload() end)
                end
            end
        end
    end

    return changes
end

-- main entry

function reportChanges(changes, playerColor)
    if #changes == 0 then
        broadcastToColor("Already up to date.", playerColor, Color.White)
    elseif #changes == 1 then
        broadcastToColor("Updated: " .. changes[1], playerColor, Color.Green)
    else
        local msg = "Updated:\n"
        for _, c in ipairs(changes) do
            msg = msg .. " - " .. c .. "\n"
        end
        broadcastToColor(msg, playerColor, Color.Green)
    end
end

function showSelectionPanel(data, model, playerColor)
    pendingData = data
    pendingModel = model
    pendingPlayerColor = playerColor
    selectionData = data.selection

    -- Initialize exclusive sets (convert 0-based to 1-based)
    exclusiveSets = {}
    if data.selection.exclusive_sets then
        for _, set in ipairs(data.selection.exclusive_sets) do
            local luaSet = {}
            for _, idx in ipairs(set) do
                table.insert(luaSet, idx + 1)
            end
            table.insert(exclusiveSets, luaSet)
        end
    end
    activeSet = 1

    -- Pre-select first option in each group of the active set
    groupSelections = {}
    if #exclusiveSets > 0 then
        for _, g in ipairs(exclusiveSets[activeSet]) do
            groupSelections[g] = 1
        end
    else
        for g = 1, #data.selection.groups do
            groupSelections[g] = 1
        end
    end

    self.UI.setXml(buildSelectionPanelXml(data.selection))
    broadcastToColor("Choose options, then click Apply.", playerColor, Color.Yellow)
end

-- True only when this card's operative has faction-rule upgrade choices in its
-- GMNotes. Operatives without upgrades get no "Choose upgrades" context item.
function hasUpgrades()
    local ok, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
    if not ok or type(data) ~= "table" then return false end
    local up = data.upgrades
    return up ~= nil and type(up.options) == "table" and #up.options > 0
end

-- True when this card's operative has the given keyword (e.g. "MOUNTED"),
-- read from GMNotes.keywords. Used to gate the "Add sprint action" item.
function hasKeyword(kw)
    local ok, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
    if not ok or type(data) ~= "table" or type(data.keywords) ~= "table" then return false end
    kw = tostring(kw):upper()
    for _, k in ipairs(data.keywords) do
        if tostring(k):upper() == kw then return true end
    end
    return false
end

-- Generic in-place injector/updater for a TAGGED block of Lua on a MODEL.
-- Strips any existing block delimited by `startMarker` .. `endMarker` (any
-- version) and appends the current `code`. When the tag is ABSENT (an older
-- model, or a first install) it simply appends -- so it works as both installer
-- and updater, and still overwrites/extends models that predate the tags. The
-- host script and script_state are left intact. Returns true if a block existed
-- (i.e. this was an update rather than a fresh install).
-- Convention going forward: wrap every injectable function block in the model
-- source with `-- START KT_<NAME> --` / `-- END KT_<NAME> --` so it can be
-- find/replaced in place with an improved version.

-- Heal a known defect in the third-party "KT Command Node UI Extender" script
-- that the extender object stamps onto models. Its getWoundPanelWidth() is
-- written with bare `if` where it needs `elseif`:
--     if wounds <= 7 then  return 60
--     if wounds <= 10 then return 80      -- should be elseif
--     if wounds <= 14 then return 100     -- should be elseif
--     elseif wounds <= 18 then return 120
--     else return 140 end
--     end
-- Those two bare ifs nest instead of chaining, so the function is 2 `end`s short.
-- On its own the missing ends are tolerated at end-of-file, but as soon as we
-- append our movement tool the deficit swallows the start of the appended code
-- and a callee inside refreshUI resolves to nil ("attempt to call a nil value"
-- -- the model loads once, then breaks the next time it is loaded).
--
-- We cannot edit the extender object, but every model carries its OWN copy of the
-- script, so we patch that copy: converting the two bare ifs to `elseif` makes the
-- two existing `end`s correctly close the if-chain and the function. Returns the
-- (possibly healed) code plus a boolean telling whether anything changed.
function healExtenderScript(code)
    if type(code) ~= "string" or code == "" then return code, false end
    if not code:find("getWoundPanelWidth", 1, true) then return code, false end
    local healed, a, b = code, 0, 0
    healed, a = healed:gsub("(return%s+60%s+)if(%s+wounds%s*<=%s*10%s+then)", "%1elseif%2")
    healed, b = healed:gsub("(return%s+80%s+)if(%s+wounds%s*<=%s*14%s+then)", "%1elseif%2")
    return healed, (a + b) > 0
end

function injectBlock(model, startMarker, endMarker, code)
    local lua = model.getLuaScript() or ""
    local existed = false
    -- 1) Remove EVERY current-format block (startMarker..endMarker). Looping so
    --    that several stacked copies (from older always-append builds) all go.
    while true do
        local s = lua:find(startMarker, 1, true)
        if not s then break end
        existed = true
        local e = lua:find(endMarker, s, true)
        if e then
            local nl = lua:find("\n", e, true)
            lua = nl and (lua:sub(1, s - 1) .. lua:sub(nl + 1)) or lua:sub(1, s - 1)
        else
            lua = lua:sub(1, s - 1)
            break
        end
    end
    -- 2) Remove any LEGACY bare-marker block. Older builds appended the tool with
    --    just "-- KT_<NAME>_V1" and no END marker, always at the END of the
    --    script, so strip from the first legacy marker to the end (this clears
    --    however many copies accumulated). Derived from startMarker:
    --    "-- START KT_SPRINT_TOOL_" -> "-- KT_SPRINT_TOOL_V1".
    local legacyMarker = startMarker:gsub("START ", "") .. "V1"
    local ls = lua:find(legacyMarker, 1, true)
    if ls then
        existed = true
        lua = lua:sub(1, ls - 1)
    end
    lua = lua:gsub("%s+$", "")
    -- Heal a malformed foreign extender script (see healExtenderScript) BEFORE
    -- appending so the extender's missing `end`s can't swallow our code.
    lua = healExtenderScript(lua)
    model.setLuaScript(lua .. "\n\n" .. code)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    return existed
end

-- Append the movement tool (SPRINT_TOOL_CODE, embedded on mounted cards) to the
-- model on top, adding "Sprint", "Turn" and "Leap" context items to it.
-- Injection-safe: the tool chains onLoad/onPickUp and never writes script_state.
function addSprintAction(playerColor)
    if type(SPRINT_TOOL_CODE) ~= "string" or SPRINT_TOOL_CODE == "" then
        broadcastToColor("Sprint tool code missing - regenerate the cards.", playerColor, Color.Orange)
        return
    end
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    -- Re-running installs the CURRENT version (doubles as an updater).
    local updating = injectBlock(model, "-- START KT_SPRINT_TOOL_", "-- END KT_SPRINT_TOOL_", SPRINT_TOOL_CODE)
    if updating then
        broadcastToColor("Sprint action updated to the latest version.", playerColor, {0.2, 0.85, 0.3})
    else
        broadcastToColor("Sprint action added. Right-click the model -> Sprint / Turn / Leap.", playerColor, {0.2, 0.85, 0.3})
    end
end

-- Append the Move tool (MOVE_TOOL_CODE, embedded on non-mounted cards) to the
-- model on top, adding a "Move" context item to it. Injection-safe: the tool
-- chains onLoad/onPickUp and never writes script_state.
function addMoveAction(playerColor)
    if type(MOVE_TOOL_CODE) ~= "string" or MOVE_TOOL_CODE == "" then
        broadcastToColor("Move tool code missing - regenerate the cards.", playerColor, Color.Orange)
        return
    end
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    -- Re-running installs the CURRENT version (doubles as an updater).
    local updating = injectBlock(model, "-- START KT_MOVE_TOOL_", "-- END KT_MOVE_TOOL_", MOVE_TOOL_CODE)
    if updating then
        broadcastToColor("Move action updated to the latest version.", playerColor, {0.2, 0.85, 0.3})
    else
        broadcastToColor("Move action added. Right-click the model -> Move.", playerColor, {0.2, 0.85, 0.3})
    end
end

-- True only when this card's operative uses an oval base (two different base
-- dimensions). Round-base operatives get no "Rotate base 90" context item.
function hasOvalBase()
    local ok, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
    if not ok or type(data) ~= "table" then return false end
    local bx, bz = parseBaseSize(data.stats and data.stats.Base)
    return bx ~= nil and bz ~= nil and not valEq(bx, bz)
end

-- Rotate the oval base 90 degrees (KT UI compatible). The KT UI extender stores
-- base = { x, z } (axis-aligned, no rotation field), so swapping x<->z is the only
-- orientation it can render. We patch the model's OWN state and reload its OWN
-- script -- never setLuaScript -- so the KT UI extender is preserved.
function rotateBase90(playerColor)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    local okd, ms = pcall(function() return JSON.decode(model.script_state or "") end)
    if not okd or type(ms) ~= "table" then
        broadcastToColor("Load stats to this model first.", playerColor, Color.Orange)
        return
    end
    local bx = ms.base and tonumber(ms.base.x)
    local bz = ms.base and tonumber(ms.base.z)
    if not (bx and bz) then
        local ok2, data = pcall(function() return JSON.decode(self.getGMNotes() or "") end)
        if ok2 and data then bx, bz = parseBaseSize(data.stats and data.stats.Base) end
    end
    if not (bx and bz) or valEq(bx, bz) then
        broadcastToColor("This operative has a round base -- nothing to rotate.", playerColor, Color.Orange)
        return
    end
    ms.base = { x = bz, z = bx }   -- swap = rotate the oval RING 90 degrees
    -- Also rotate the operative FRONT: Sprint/Turn/Leap derive their heading from
    -- the transform + a per-model kt_front offset (0/90/180/270). Bumping it here
    -- keeps the movement direction aligned with the (now-rotated) long axis and
    -- lets players correct sculpts that otherwise run tail-first. KTUI ignores
    -- this key but preserves it (loadState/saveState round-trip the whole table).
    ms.kt_front = ((tonumber(ms.kt_front) or 0) + 90) % 360
    model.script_state = JSON.encode(ms)
    model.reload()
    broadcastToColor(string.format("Base rotated 90 (now %sx%s, front +%d).", tostring(bz), tostring(bx), ms.kt_front), playerColor, Color.Green)
end

function proceedLoad(playerColor, data, model, ignoreWeapons)
    if (not ignoreWeapons) and data.selection and data.selection.groups and #data.selection.groups > 0 then
        showSelectionPanel(data, model, playerColor)
    else
        local changes = diffAndApply(model, data, playerColor)
        reportChanges(changes, playerColor)
        pendingData = nil
        pendingModel = nil
        pendingPlayerColor = nil
        -- No loadout popup: the stats step finished synchronously, so advance the
        -- "Load everything" chain now (no-op unless it is active).
        if loadEverythingActive then afterStatsLoaded(playerColor) end
    end
end

-- ===== "Load everything" orchestrator =====
-- One click runs the full setup IN ORDER: load stats (forcing the loadout popup
-- when the operative has one) -> apply faction upgrades if any -> faction-rule
-- popup if any (chapter tactics / gore tanks) -> operative counters if any ->
-- movement. The stats, upgrade and faction-rule steps use ASYNC selection
-- popups, so the chain is advanced from their Apply handlers, guarded by this
-- flag; the counters + movement steps are synchronous. Any Cancel aborts the
-- chain. The individual menu items still work standalone. (Rotate base excluded.)
--
-- Each stats/counters/movement step rewrites the model's Lua and reload()s it
-- (~10 frames later). Reloads that stack in the same frame make TTS leave TWO
-- overlapping copies of the model, so between every mutate+reload step we WAIT a
-- short window for the previous reload to settle. Each step re-acquires the
-- model via findModelOnCard(), so it always works on the freshly reloaded object.
loadEverythingActive = false
local LOAD_EVERYTHING_STEP_FRAMES = 45   -- window between mutate+reload steps (the composed KTUI script is large -> reload needs longer to settle)

-- Run nextFn(playerColor) after a short settle window, if the chain is still active.
function loadEverythingWait(nextFn, playerColor)
    if not loadEverythingActive then return end
    Wait.frames(function()
        if loadEverythingActive then nextFn(playerColor) end
    end, LOAD_EVERYTHING_STEP_FRAMES)
end

function loadEverything(playerColor)
    loadEverythingActive = true
    loadStatsToModel(playerColor)          -- continues via afterStatsLoaded(...)
end

-- After the STATS step (called from onApplySelection and the sync path above).
function afterStatsLoaded(playerColor)
    if not loadEverythingActive then return end
    if hasUpgrades() then
        chooseUpgrades(playerColor)        -- async -> continues via afterUpgradesLoaded
    else
        -- Stats just reloaded the model; settle before the next step.
        loadEverythingWait(afterFactionRuleStep, playerColor)
    end
end

-- After the UPGRADES step (Exodite <archetype> UPGRADE picks). Continue to the
-- faction-rule popup step.
function afterUpgradesLoaded(playerColor)
    if not loadEverythingActive then return end
    -- Upgrades just refreshed/reloaded the model; settle before the next step.
    loadEverythingWait(afterFactionRuleStep, playerColor)
end

-- Faction-rule popup step (e.g. AoD "Chapter Tactics", Goremongers "Gore Tanks"),
-- generated as applyFactionRule() on teams that use the select-1/2 popup. It is
-- an ASYNC popup: its Apply handler resumes via afterFactionRuleLoaded and its
-- Cancel aborts the chain. Cards without a popup skip straight ahead.
function afterFactionRuleStep(playerColor)
    if not loadEverythingActive then return end
    if type(applyFactionRule) == "function" then
        applyFactionRule(playerColor)      -- async -> continues via afterFactionRuleLoaded
    else
        afterFactionRuleLoaded(playerColor)
    end
end

-- After the FACTION-RULE popup (or when there is none). Continue to counters.
function afterFactionRuleLoaded(playerColor)
    if not loadEverythingActive then return end
    loadEverythingWait(afterCountersStep, playerColor)
end

-- Operative counters are injected by an APPENDED feature block. A card may have
-- the MULTI counter menu (addOperativeCountersToModel, e.g. Exodite) OR the
-- SINGLE counter (addOperativeCounterToModel, e.g. Goremongers "Gore Tank") --
-- run whichever exists. Both are synchronous (model rewrite + reload), so settle
-- before movement; when neither exists, go straight to movement.
function afterCountersStep(playerColor)
    if not loadEverythingActive then return end
    local didCounter = false
    if type(addOperativeCountersToModel) == "function" then
        addOperativeCountersToModel(playerColor)
        didCounter = true
    end
    if type(addOperativeCounterToModel) == "function" then
        addOperativeCounterToModel(playerColor)
        didCounter = true
    end
    if didCounter then
        loadEverythingWait(afterCountersLoaded, playerColor)
    else
        afterCountersLoaded(playerColor)
    end
end

-- After the COUNTERS step. Adds the movement action (the final step) and ends.
function afterCountersLoaded(playerColor)
    if not loadEverythingActive then return end
    loadEverythingActive = false
    if type(SPRINT_TOOL_CODE) == "string" and hasKeyword("MOUNTED") then
        addSprintAction(playerColor)
    elseif type(MOVE_TOOL_CODE) == "string" then
        addMoveAction(playerColor)
    end
end

-- Abort the chain (called from the Cancel handlers of either popup).
function cancelLoadEverything()
    loadEverythingActive = false
end

-- ===== Faction-rule upgrades (mounted operatives pick N of M) =====

function chooseUpgrades(playerColor)
    local raw = self.getGMNotes()
    local ok, data = pcall(function() return JSON.decode(raw or "") end)
    if not ok or not data then
        broadcastToColor("No stat data on this card.", playerColor, Color.Red)
        return
    end
    local up = data.upgrades
    if not up or not up.options or #up.options == 0 then
        broadcastToColor("This datacard has no upgrade choices.", playerColor, Color.Orange)
        return
    end
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place the model on this card first.", playerColor, Color.Orange)
        return
    end
    upgradeOptions = up.options
    upgradeSelect = tonumber(up.select) or 2
    upgradeChosen = {}
    upgradeModel = model
    upgradeData = data
    upgradePlayerColor = playerColor
    self.UI.setXml(buildUpgradePanelXml(up.options, upgradeSelect))
    broadcastToColor(string.format("Select %d upgrades, then click Apply.", upgradeSelect), playerColor, Color.Yellow)
end

function buildUpgradePanelXml(options, selectN)
    local rows = ""
    for i, opt in ipairs(options) do
        local label = opt.name or ("Upgrade " .. i)
        label = label:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
        rows = rows .. string.format(
            '<Toggle id="upg_%d" isOn="false" onValueChanged="onUpgradeToggle" '
            .. 'fontSize="11" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="18" toggleHeight="18">%s</Toggle>\n', i, label)
    end
    local h = 74 + #options * 26
    return string.format([[
<Panel id="upgradePanel" active="true" width="264" height="%d"
       color="rgba(0,0,0,0.92)" padding="6 6 6 6" position="0 0 -50"
       rotation="0 0 180" allowDragging="true">
  <VerticalLayout spacing="3" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900" alignment="MiddleCenter" preferredHeight="20">Choose %d Upgrades</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="btnUpgApply" onClick="onApplyUpgrades" fontSize="10" fontStyle="Bold" colors="#2E7D32|#388E3C|#1B5E20|#555555" textColor="#FFFFFF">Apply</Button>
      <Button id="btnUpgCancel" onClick="onCancelUpgrades" fontSize="10" colors="#C62828|#D32F2F|#B71C1C|#555555" textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], h, selectN, rows)
end

function _upgradeCount()
    local n = 0
    for _ in pairs(upgradeChosen) do n = n + 1 end
    return n
end

function onUpgradeToggle(player, value, id)
    local i = tonumber(id:match("upg_(%d+)"))
    if not i then return end
    if value == "True" then
        if _upgradeCount() >= upgradeSelect then
            -- Enforce the limit: bounce this toggle back off.
            self.UI.setAttribute(id, "isOn", "false")
            broadcastToColor(string.format("Pick exactly %d -- deselect one first.", upgradeSelect), upgradePlayerColor, Color.Orange)
            return
        end
        upgradeChosen[i] = true
    else
        upgradeChosen[i] = nil
    end
end

function onApplyUpgrades(player, value, id)
    if _upgradeCount() ~= upgradeSelect then
        broadcastToColor(string.format("Select exactly %d upgrades.", upgradeSelect), upgradePlayerColor, Color.Orange)
        return
    end
    self.UI.setXml("")
    if not upgradeData or not upgradeModel or not upgradeOptions then return end
    local data = upgradeData
    data.abilities = data.abilities or {}
    local chosenNames = {}
    for i in pairs(upgradeChosen) do
        local opt = upgradeOptions[i]
        if opt then
            table.insert(data.abilities, { name = opt.name, text = opt.text })
            table.insert(chosenNames, opt.name)
        end
    end
    local changes = diffAndApply(upgradeModel, data, nil)
    broadcastToColor("Upgrades applied: " .. table.concat(chosenNames, ", "), upgradePlayerColor, Color.Green)
    local pc = upgradePlayerColor
    upgradeChosen = {}
    upgradeModel = nil
    upgradeData = nil
    upgradeOptions = nil
    -- Advance the "Load everything" chain to the movement step (no-op unless active).
    if loadEverythingActive then afterUpgradesLoaded(pc) end
end

function onCancelUpgrades(player, value, id)
    self.UI.setXml("")
    cancelLoadEverything()
    broadcastToColor("Upgrade selection cancelled.", upgradePlayerColor or (player and player.color) or "White", Color.White)
    upgradeChosen = {}
    upgradeModel = nil
    upgradeData = nil
    upgradeOptions = nil
end

function loadStatsToModelAll(playerColor)
    local raw = self.getGMNotes()
    if raw == nil or raw == "" then
        broadcastToColor("No stat data on this card.", playerColor, Color.Red)
        return
    end

    local ok, data = pcall(function() return JSON.decode(raw) end)
    if not ok or data == nil then
        broadcastToColor("Failed to parse card data.", playerColor, Color.Red)
        return
    end

    -- Base (incl. oval) applies in its default orientation; use "Rotate base 90"
    -- afterwards if a mesh needs the oval turned.
    local modelAll = findModelOnCard()
    if modelAll == nil then
        broadcastToColor("Place a model on this card first.", playerColor, Color.Orange)
        return
    end
    proceedLoad(playerColor, data, modelAll, true)
end

function loadStatsToModel(playerColor)
    local raw = self.getGMNotes()
    if raw == nil or raw == "" then
        broadcastToColor("No stat data on this card.", playerColor, Color.Red)
        return
    end

    local ok, data = pcall(function() return JSON.decode(raw) end)
    if not ok or data == nil then
        broadcastToColor("Failed to parse card data.", playerColor, Color.Red)
        return
    end

    -- Base (incl. oval) applies in its default orientation; use "Rotate base 90"
    -- afterwards if a mesh needs the oval turned.
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a model on this card first.", playerColor, Color.Orange)
        return
    end
    proceedLoad(playerColor, data, model, false)
end

NODE_COUNTER_SETUP = [====[{"goremongers": {"name": "Gore Tank"}}]====]

function ktCommandNodeAddCounters(params)
    local findModelOnCard = function() return params.model end
    if params.team == "goremongers" then


-- ===== OPERATIVE COUNTER: GORE TANK =====

OC_NAME = "Gore Tank"
OC_INIT_VALUE = 0
OC_MIN_VAL = 0
OC_MAX_VAL = 2

OC_HELPER_FUNCS = [==[
--OC1_HELP:START

-- Gore Tank Counter (auto-injected)
function getOperativeCounterImage()
  if not state or not state.operative_counter then return "oc_asset_0" end
  local v = state.operative_counter.current or 0
  local assets = {[0]="oc_asset_0", [1]="oc_asset_1", [2]="oc_asset_2"}
  return assets[v] or "oc_asset_0"
end

function change_operative_counter(player, value, id)
  if not state.operative_counter then return end
  local current = state.operative_counter.current or 0
  local maxv = state.operative_counter.max or 2
  local minv = state.operative_counter.min or 0
  if value == "-1" then
    if current > minv then current = current - 1 end
  elseif value == "-2" then
    if current < maxv then current = current + 1 end
  end
  state.operative_counter.current = current
  if refreshUI then refreshUI() end
  local labels = {[0]="Empty", [1]="Half", [2]="Full"}
  broadcastToColor("Gore Tank: " .. (labels[current] or "?"), player.color, Color.Yellow)
end

--OC1_HELP:END
]==]

OC_ASSET_LINES = [==[
    {name="oc_asset_0", url=[=[https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/goremongers/tokens/goremongers-gore-tank-empty.png]=]},
    {name="oc_asset_1", url=[=[https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/goremongers/tokens/goremongers-gore-tank-half.png]=]},
    {name="oc_asset_2", url=[=[https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/goremongers/tokens/goremongers-gore-tank-full.png]=]},
]==]

OC_PANEL_XML = "\n    <Panel color=\"#80808000\" outline=\"#FFFF00\" outlineSize=\"3 3\" width=\"45\" height=\"45\" offsetXY=\"0 -10\">"
    .. "\n      <Image id=\"ktcnid-status-operative-counter\" image=\""
    .. "]]..getOperativeCounterImage()..[["
    .. "\" preserveAspect=\"true\" rectAlignment=\"MiddleCenter\" onClick=\"change_operative_counter\" />"
    .. "\n    </Panel>"

-- Strip helpers so re-applying UPDATES in place (mirrors the sprint/move and
-- multi-counter behaviour) instead of bailing with "already has".
function ocStrip1(s, a, b)
    while true do
        local i = s:find(a, 1, true)
        if not i then break end
        local j = s:find(b, i, true)
        if not j then return s:sub(1, i - 1) end
        s = s:sub(1, i - 1) .. s:sub(j + #b)
    end
    return s
end

function ocStripPanelById1(s, id)
    while true do
        local idpos = s:find(id, 1, true)
        if not idpos then break end
        local ps, from = nil, 1
        while true do
            local p = s:find("<Panel", from, true)
            if not p or p > idpos then break end
            ps, from = p, p + 1
        end
        local pe = s:find("</Panel>", idpos, true)
        if not ps or not pe then break end
        s = s:sub(1, ps - 1) .. s:sub(pe + 8)
    end
    return s
end

function ocStripLines1(s, sub)
    local out = {}
    for line in (s .. "\n"):gmatch("([^\n]*)\n") do
        if not line:find(sub, 1, true) then out[#out + 1] = line end
    end
    return table.concat(out, "\n")
end

function addOperativeCounterToModel(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

    local modelLua = model.getLuaScript() or ""
    if modelLua == "" then
        broadcastToColor("Model has no Lua script (not a KTUI model?).", playerColor, Color.Red)
        return
    end

    local existed = modelLua:find("ktcnid%-status%-operative%-counter") ~= nil

    -- Remove any prior copy (old OR new) then (re)inject.
    modelLua = ocStripPanelById1(modelLua, 'id="ktcnid-status-operative-counter"')
    modelLua = ocStripLines1(modelLua, 'name="oc_asset_')
    modelLua = ocStrip1(modelLua, "--OC1_HELP:START", "--OC1_HELP:END")

    local xmlPattern = "(<HorizontalLayout spacing=\"3\" width=\"@totalAtt\")"
    if modelLua:find(xmlPattern) then
        modelLua = modelLua:gsub(xmlPattern, OC_PANEL_XML .. "\n    %1")
    else
        broadcastToColor("Could not find attachment layout in model.", playerColor, Color.Red)
        return
    end

    local bundlePattern = "({name=\"Wound_red\"[^\n]+)"
    if modelLua:find(bundlePattern) then
        modelLua = modelLua:gsub(bundlePattern, "%1" .. OC_ASSET_LINES)
    end

    modelLua = modelLua .. OC_HELPER_FUNCS

    local modelState = model.script_state or "{}"
    local ok, mState = pcall(function() return JSON.decode(modelState) end)
    if not ok or not mState then mState = {} end
    local prev = mState.operative_counter
    local cur = (prev and prev.current) or OC_INIT_VALUE
    if cur < OC_MIN_VAL then cur = OC_MIN_VAL end
    if cur > OC_MAX_VAL then cur = OC_MAX_VAL end
    mState.operative_counter = { name = OC_NAME, current = cur, min = OC_MIN_VAL, max = OC_MAX_VAL }
    model.script_state = JSON.encode(mState)

    model.setLuaScript(modelLua)
    Wait.frames(function() model.reload() end, 10)

    if existed then
        broadcastToColor("Updated " .. OC_NAME .. " counter.", playerColor, Color.Green)
    else
        broadcastToColor("Added " .. OC_NAME .. " counter to model!", playerColor, Color.Green)
    end
end

local ocBaseOnLoad = onLoad
function onLoad()
    if ocBaseOnLoad then ocBaseOnLoad() end
    self.addContextMenuItem("Add " .. OC_NAME, addOperativeCounterToModel)
end

-- ===== END OPERATIVE COUNTER =====

        addOperativeCounterToModel(params.playerColor)
        return true
    end
    return false
end

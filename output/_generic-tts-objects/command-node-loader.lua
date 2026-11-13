KTUI_MODELSCRIPT_VERSION = "96a77fb50d93"

KTUI_MODELSCRIPT = [==[KT_MODELSCRIPT_VERSION = "96a77fb50d93"

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
-- (no active extension code yet)
-- END KT_EXTENSION_V1 --
]==]

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

function diffAndApply(model, data, playerColor)
    local changes = {}

    local msRaw = model.script_state
    local ms = {}
    if msRaw and msRaw ~= "" then
        local ok, parsed = pcall(function() return JSON.decode(msRaw) end)
        if ok and parsed then ms = parsed end
    end

    -- What kind of model is this?
    --  * isKtui    : already a KTUI mini of ANY kind (our bundled one OR the real
    --                KT UI extender). If so we NEVER replace its script -- we just
    --                update its state in place so a fancy extender keeps its UI.
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
    -- the current composed script (re)installed. A real KT UI extender mini
    -- (KTUIMini but not managed) is left alone -- we only update its state and
    -- refresh in place (never overwrite the extender's script).
    -- playerColor (optional) is used to assign the KTUI owner on a (re)stamp.
    local needsScript = ((not isKtui) or ktuiOutdated) and KTUI_MODELSCRIPT ~= nil and KTUI_MODELSCRIPT ~= ""
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
            model.setLuaScript(KTUI_MODELSCRIPT)
            if not model.hasTag("KTUIMini") then model.addTag("KTUIMini") end
            model.addTag("KTUIMiniDatacard")
            table.insert(changes, ktuiOutdated and "Upgraded KTUI script" or "Prepared model for KTUI extender")
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

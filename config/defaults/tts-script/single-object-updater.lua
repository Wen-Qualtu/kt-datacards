-- kt-datacards: Single object updater (minimal)
-- Adds a right-click "Update" on cards and token dispensers.
-- It looks up the team's object-urls.json and refreshes this object's image
-- URLs in place (new cache-busting ?v= postfix). It does NOT download the full
-- team box JSON, so it stays tiny and cheap to spawn.

local KTU_REPO = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"

local function ktu_strip(url)
  if not url or url == "" then return "" end
  return (string.match(url, "^[^?]+") or url)
end

-- Path-only signature so the same image matches regardless of ?v= cache-bust.
local function ktu_sig(url)
  local clean = ktu_strip(url)
  if clean == "" then return "" end
  return string.lower(string.match(clean, "(/output/[^%s]+)$") or clean)
end

local function ktu_team_from_url(url)
  return string.match(ktu_strip(url), "/output/([^/]+)/")
end

local function ktu_cache_bust(url, value)
  if not url or url == "" then return url end
  local sep = string.find(url, "?", 1, true) and "&" or "?"
  return url .. sep .. "v=" .. tostring(value)
end

-- Returns kind ("card" | "token"), and the current face/back or mesh/texture.
local function ktu_self_info()
  local data = self.getData()
  if type(data) ~= "table" then return nil end

  if data.Name == "Card" or data.Name == "CardCustom" then
    local custom = self.getCustomObject() or {}
    local face = custom.FaceURL or custom.face or ""
    local back = custom.BackURL or custom.back or ""
    if face == "" and type(data.CustomDeck) == "table" then
      for _, e in pairs(data.CustomDeck) do
        if type(e) == "table" then face = e.FaceURL or face; back = e.BackURL or back end
      end
    end
    if face == "" then return nil end
    return { kind = "card", face = face, back = back, src = face }
  elseif data.Name == "Custom_Model_Infinite_Bag" or data.Name == "Custom_Model" then
    local mesh = ((data.CustomMesh or {}).MeshURL) or ""
    local tex = ((data.CustomMesh or {}).DiffuseURL) or ""
    if tex == "" and type(data.ContainedObjects) == "table" and data.ContainedObjects[1] then
      tex = ((data.ContainedObjects[1].CustomImage or {}).ImageURL) or ""
    end
    local src = mesh ~= "" and mesh or tex
    if src == "" then return nil end
    return { kind = "token", mesh = mesh, tex = tex, src = src }
  end
  return nil
end

local function ktu_find_match(objects, info)
  if type(objects) ~= "table" then return nil end
  for _, o in ipairs(objects) do
    if info.kind == "card" and o.face_url then
      local fs, bs = ktu_sig(info.face), ktu_sig(info.back)
      if (fs ~= "" and fs == ktu_sig(o.face_url))
        or (bs ~= "" and bs == ktu_sig(o.back_url)) then
        return o
      end
    elseif info.kind == "token" and (o.mesh_url or o.texture_url) then
      local ms, ts = ktu_sig(info.mesh), ktu_sig(info.tex)
      if (ms ~= "" and ms == ktu_sig(o.mesh_url))
        or (ts ~= "" and ts == ktu_sig(o.texture_url)) then
        return o
      end
    end
  end
  return nil
end

local function ktu_apply(info, meta, playerColor)
  local who = playerColor or "White"
  local custom = self.getCustomObject() or {}

  if info.kind == "card" then
    -- TTS setCustomObject for CardCustom uses lowercase face/back at runtime;
    -- the uppercase FaceURL/BackURL only appear in saved JSON. Set both so the
    -- live object actually re-fetches the new image.
    if meta.face_url then custom.face = meta.face_url; custom.FaceURL = meta.face_url end
    if meta.back_url then custom.back = meta.back_url; custom.BackURL = meta.back_url end
  else
    if meta.mesh_url then custom.MeshURL = meta.mesh_url; custom.mesh = meta.mesh_url end
    if meta.texture_url then custom.DiffuseURL = meta.texture_url; custom.diffuse = meta.texture_url end
  end

  local ok = pcall(function() self.setCustomObject(custom) end)
  if not ok then
    broadcastToColor("Update failed: could not set URLs", who, {1, 0.5, 0})
    return
  end
  pcall(function() self.reload() end)
  broadcastToColor("Object updated", who, {0, 1, 0})
end

function click_update_single_object(playerColor)
  local who = playerColor or "White"
  local info = ktu_self_info()
  if not info then
    broadcastToColor("Update is supported on cards and token dispensers only", who, {1, 0.5, 0})
    return
  end

  local team = ktu_team_from_url(info.src)
  if not team or team == "" then
    broadcastToColor("Could not determine team for this object", who, {1, 0.5, 0})
    return
  end

  broadcastToColor("Checking update for this object...", who, {1, 1, 0})

  local url = ktu_cache_bust(KTU_REPO .. "/output/" .. team .. "/" .. team .. "-object-urls.json", os.time())
  WebRequest.get(url, function(req)
    if req.is_error then
      broadcastToColor("Could not fetch object metadata: " .. tostring(req.error), who, {1, 0.5, 0})
      return
    end
    local ok, meta = pcall(function() return JSON.decode(req.text) end)
    if not ok or type(meta) ~= "table" then
      broadcastToColor("Could not parse object metadata", who, {1, 0.5, 0})
      return
    end

    local match = ktu_find_match(meta.objects, info)
    if not match then
      broadcastToColor("No matching metadata found for this object", who, {1, 0.5, 0})
      return
    end

    -- Up-to-date check: same image path AND same ?v= cache-bust on both sides.
    local current = info.kind == "card" and info.face or info.src
    local remote = info.kind == "card" and match.face_url or (match.mesh_url or match.texture_url)
    if ktu_strip(current) == ktu_strip(remote)
      and string.match(current or "", "[?&]v=(%d+)") == string.match(remote or "", "[?&]v=(%d+)") then
      broadcastToColor("This object is already up to date", who, {0, 1, 0})
      return
    end

    ktu_apply(info, match, who)
  end)
end

function registerSingleObjectUpdaterMenu()
  if _ktu_update_menu_registered then return end
  _ktu_update_menu_registered = true
  self.addContextMenuItem("Update", function(playerColor)
    click_update_single_object(playerColor)
  end)
end

local _ktu_prev_onLoad = onLoad
function onLoad(...)
  if _ktu_prev_onLoad then pcall(_ktu_prev_onLoad, ...) end
  registerSingleObjectUpdaterMenu()
end

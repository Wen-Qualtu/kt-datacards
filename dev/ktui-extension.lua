-- KT model-side extension (appended AFTER the healed KTUI extender script).
-- This is OUR code that rides on top of the real extender model script. It is
-- composed into the single KTUI_MODELSCRIPT our cards stamp onto a model.
--
-- Append-safety: this only works because the composer heals getWoundPanelWidth
-- first (otherwise the extender's missing `end`s swallow everything below).
--
-- POC scope: prove appended code runs AND the extender UI/state still works
-- (chained onLoad, no script_state clobber). Productionization grows this file
-- to carry our move/sprint/callout hooks (the blocks the cards inject today).

-- START KT_EXTENSION_V1 --
do
  -- Chain onLoad so the extender's own onLoad (loadState + UI + KTUIMini tag)
  -- runs first, then we add our hooks. Never touches script_state.
  local _kt_prev_onLoad = onLoad
  function onLoad(...)
    if _kt_prev_onLoad then pcall(_kt_prev_onLoad, ...) end
    self.addContextMenuItem("KT: extension OK", function(pc)
      local nm = self.getName()
      printToAll("KT extension live on " .. (nm ~= "" and nm or "operative"), { 0.2, 0.85, 0.3 })
    end)
  end
end
-- END KT_EXTENSION_V1 --

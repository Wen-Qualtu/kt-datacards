# KT Command Node UI Extender — bug report & suggestion

For the maintainer of the **KT Command Node UI Extender** (the object that stamps
the fancy UI script onto models). Two items:

1. A **confirmed bug** in `getWoundPanelWidth()` (malformed `if` chain).
2. An optional **feature suggestion**: expose the movement actions as global functions.

---

## 1. Bug: `getWoundPanelWidth()` is missing two `end`s

### Current code (as shipped)

```lua
local function getWoundPanelWidth()
  local wounds = state.stats and state.stats.Wounds or 0
  if wounds <= 7 then
    return 60
  if wounds <= 10 then      -- <-- should be elseif
    return 80
  if wounds <= 14 then      -- <-- should be elseif
    return 100
  elseif wounds <= 18 then
    return 120
  else
    return 140
  end
end
```

### The problem

The 2nd and 3rd branches use bare `if` instead of `elseif`, so they **nest**
instead of chaining. Counting openers vs closers:

- `if <= 7` (open) → `if <= 10` (open, nested) → `if <= 14` (open, nested) …
- The inner `if <= 14 … elseif … else … end` consumes the **first** `end`.
- The **second** `end` closes the `if <= 10`.
- The `if <= 7` block and the **function itself** are never closed — the function
  is **two `end`s short**.

Moonsharp (TTS's Lua) tolerates the missing `end`s when this is at the very end of
the script, so the mod loads and the HP bar renders. But the moment **any code is
appended after this script** (e.g. another mod injecting a helper onto the same
model), the deficit swallows the start of that appended code. A callee inside
`refreshUI()` then resolves to `nil`, producing:

```
attempt to call a nil value
```

…in `refreshUI` — typically **intermittent**: the model loads once, then breaks
the next time it is loaded, and it tends to show up on higher-wound operatives.

### The fix

Change the two bare `if` to `elseif`. No other change needed — the two existing
`end`s then correctly close the if-chain and the function:

```lua
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
```

This is behaviour-identical for the normal case (it already returned the right
widths where it worked) but is now syntactically balanced, so appended code no
longer breaks `refreshUI`.

---

## 2. Suggestion: make the movement actions global

Right now movement logic (Move / Sprint / Turn / Leap) that other mods add tends
to be **embedded per-model**, which is what collides with the script above and
gets wiped whenever the extender re-stamps a model. If the extender (or the mod's
Global) exposed the movement actions as **global functions**, it would be more
robust and would let you theme them **per player color**.

### Model side — context menu still triggers it

```lua
self.addContextMenuItem("Sprint", function(player_color)
    Global.call("KTMT_startSprint", { model = self.getGUID(), color = player_color })
end)
```

- `addContextMenuItem`'s callback receives `player_color` (whoever clicked) — the
  hook for per-player behaviour.
- The menu item still lives on the model, so the trigger UX is unchanged.

### Global side — the logic lives once

```lua
function KTMT_startSprint(params)
    local model = getObjectFromGUID(params.model)
    local color = params.color            -- who clicked
    -- draw the movement vectors tinted for `color`,
    -- gate control so only that player can drive it, etc.
end
```

### Notes / caveats

- `Global.call(name, arg)` passes a **single serializable table** — pass the
  model's **GUID** (a string) and re-resolve with `getObjectFromGUID`.
- Keyword gating (e.g. Sprint only for `MOUNTED`) can live either on the model
  (decide which menu item to add) or in the global function (read the model's
  `script_state` / tags first).
- Vector rendering stays per-model (`model.setVectorLines(...)`), but the color
  can now come from the clicking player.
- Benefit: with the logic global, it **survives the extender re-stamping the
  model**, so downstream mods no longer have to re-inject their code every time
  the extender is used.

AgentEngine = AgentEngine or {
    is_busy = false,
    host = "127.0.0.1",
    port = 12345,
    socket_timeout_sec = 0.12,
    protocol_version = "1.0.0",
    last_request_fingerprint = nil,
    last_response_action = nil,
    last_response_message = nil,
    pending_transition = nil,
    pending_transition_max_polls = 180,
    noop_waiting = false,
    noop_wait_fingerprint = nil,
    noop_poll_counter = 0,
    noop_poll_stride = 10,
    game_update_wrapped = false,
    logged_messages = {}
}

local function try_require(name)
    local ok, module = pcall(require, name)
    if ok then
        return module
    end
    return nil
end

local socket = try_require("socket")

local function codepoint_to_utf8(codepoint)
    if codepoint <= 0x7F then
        return string.char(codepoint)
    end
    if codepoint <= 0x7FF then
        local b1 = 0xC0 + math.floor(codepoint / 0x40)
        local b2 = 0x80 + (codepoint % 0x40)
        return string.char(b1, b2)
    end
    if codepoint <= 0xFFFF then
        local b1 = 0xE0 + math.floor(codepoint / 0x1000)
        local b2 = 0x80 + (math.floor(codepoint / 0x40) % 0x40)
        local b3 = 0x80 + (codepoint % 0x40)
        return string.char(b1, b2, b3)
    end
    if codepoint <= 0x10FFFF then
        local b1 = 0xF0 + math.floor(codepoint / 0x40000)
        local b2 = 0x80 + (math.floor(codepoint / 0x1000) % 0x40)
        local b3 = 0x80 + (math.floor(codepoint / 0x40) % 0x40)
        local b4 = 0x80 + (codepoint % 0x40)
        return string.char(b1, b2, b3, b4)
    end
    return "?"
end

local JsonFallback = {}

local JSON_OBJECT_MT = { __json_object = true }

local function json_object(value)
    return setmetatable(value or {}, JSON_OBJECT_MT)
end

local function is_forced_json_object(value)
    local mt = getmetatable(value)
    return mt ~= nil and mt.__json_object == true
end

local function json_escape_string(value)
    local replacements = {
        ['\\'] = '\\\\',
        ['"'] = '\\"',
        ['\b'] = '\\b',
        ['\f'] = '\\f',
        ['\n'] = '\\n',
        ['\r'] = '\\r',
        ['\t'] = '\\t'
    }

    return value:gsub('[%z\1-\31\\"]', function(ch)
        return replacements[ch] or string.format("\\u%04x", ch:byte())
    end)
end

local function is_json_array(value)
    local count = 0
    local max_index = 0
    for key, _ in pairs(value) do
        if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
            return false, 0
        end
        count = count + 1
        if key > max_index then
            max_index = key
        end
    end
    return max_index == count, max_index
end

local function json_encode_value(value, seen)
    local value_type = type(value)

    if value_type == "nil" then
        return "null"
    end
    if value_type == "boolean" then
        return value and "true" or "false"
    end
    if value_type == "number" then
        if value ~= value or value == math.huge or value == -math.huge then
            return "null"
        end
        return tostring(value)
    end
    if value_type == "string" then
        return '"' .. json_escape_string(value) .. '"'
    end
    if value_type ~= "table" then
        return "null"
    end

    if seen[value] then
        return "null"
    end
    seen[value] = true

    local is_array, array_len
    if is_forced_json_object(value) then
        is_array = false
        array_len = 0
    else
        is_array, array_len = is_json_array(value)
    end
    local output = {}
    if is_array then
        for i = 1, array_len do
            output[#output + 1] = json_encode_value(value[i], seen)
        end
        seen[value] = nil
        return "[" .. table.concat(output, ",") .. "]"
    end

    local keys = {}
    for key, _ in pairs(value) do
        if type(key) == "string" then
            keys[#keys + 1] = key
        end
    end
    table.sort(keys)
    for _, key in ipairs(keys) do
        output[#output + 1] = '"' .. json_escape_string(key) .. '":' .. json_encode_value(value[key], seen)
    end
    seen[value] = nil
    return "{" .. table.concat(output, ",") .. "}"
end

function JsonFallback.encode(value)
    return json_encode_value(value, {})
end

local function json_decode_error(text, pos, reason)
    error("JSON decode error at position " .. tostring(pos) .. ": " .. tostring(reason) .. " in " .. text:sub(math.max(1, pos - 10), math.min(#text, pos + 30)))
end

local function skip_whitespace(text, pos)
    while pos <= #text do
        local ch = text:sub(pos, pos)
        if ch ~= " " and ch ~= "\n" and ch ~= "\r" and ch ~= "\t" then
            break
        end
        pos = pos + 1
    end
    return pos
end

local parse_json_value

local function parse_json_string(text, pos)
    pos = pos + 1
    local output = {}
    while pos <= #text do
        local ch = text:sub(pos, pos)
        if ch == '"' then
            return table.concat(output), pos + 1
        end
        if ch == "\\" then
            local esc = text:sub(pos + 1, pos + 1)
            if esc == '"' or esc == "\\" or esc == "/" then
                output[#output + 1] = esc
                pos = pos + 2
            elseif esc == "b" then
                output[#output + 1] = "\b"
                pos = pos + 2
            elseif esc == "f" then
                output[#output + 1] = "\f"
                pos = pos + 2
            elseif esc == "n" then
                output[#output + 1] = "\n"
                pos = pos + 2
            elseif esc == "r" then
                output[#output + 1] = "\r"
                pos = pos + 2
            elseif esc == "t" then
                output[#output + 1] = "\t"
                pos = pos + 2
            elseif esc == "u" then
                local hex = text:sub(pos + 2, pos + 5)
                if #hex ~= 4 or not hex:match("^[0-9a-fA-F]+$") then
                    json_decode_error(text, pos, "invalid unicode escape")
                end
                output[#output + 1] = codepoint_to_utf8(tonumber(hex, 16))
                pos = pos + 6
            else
                json_decode_error(text, pos, "invalid escape sequence")
            end
        else
            output[#output + 1] = ch
            pos = pos + 1
        end
    end
    json_decode_error(text, pos, "unterminated string")
end

local function parse_json_number(text, pos)
    local match = text:sub(pos):match("^-?%d+%.?%d*[eE]?[+-]?%d*")
    if not match or match == "" then
        json_decode_error(text, pos, "invalid number")
    end
    local numeric = tonumber(match)
    if numeric == nil then
        json_decode_error(text, pos, "invalid numeric value")
    end
    return numeric, pos + #match
end

local function parse_json_array(text, pos)
    local output = {}
    pos = skip_whitespace(text, pos + 1)
    if text:sub(pos, pos) == "]" then
        return output, pos + 1
    end

    while pos <= #text do
        local value
        value, pos = parse_json_value(text, pos)
        output[#output + 1] = value
        pos = skip_whitespace(text, pos)
        local ch = text:sub(pos, pos)
        if ch == "]" then
            return output, pos + 1
        end
        if ch ~= "," then
            json_decode_error(text, pos, "expected ',' or ']'")
        end
        pos = skip_whitespace(text, pos + 1)
    end

    json_decode_error(text, pos, "unterminated array")
end

local function parse_json_object(text, pos)
    local output = {}
    pos = skip_whitespace(text, pos + 1)
    if text:sub(pos, pos) == "}" then
        return output, pos + 1
    end

    while pos <= #text do
        if text:sub(pos, pos) ~= '"' then
            json_decode_error(text, pos, "expected string key")
        end
        local key
        key, pos = parse_json_string(text, pos)
        pos = skip_whitespace(text, pos)
        if text:sub(pos, pos) ~= ":" then
            json_decode_error(text, pos, "expected ':' after object key")
        end
        pos = skip_whitespace(text, pos + 1)
        output[key], pos = parse_json_value(text, pos)
        pos = skip_whitespace(text, pos)
        local ch = text:sub(pos, pos)
        if ch == "}" then
            return output, pos + 1
        end
        if ch ~= "," then
            json_decode_error(text, pos, "expected ',' or '}'")
        end
        pos = skip_whitespace(text, pos + 1)
    end

    json_decode_error(text, pos, "unterminated object")
end

function parse_json_value(text, pos)
    pos = skip_whitespace(text, pos)
    local ch = text:sub(pos, pos)

    if ch == '"' then
        return parse_json_string(text, pos)
    end
    if ch == "{" then
        return parse_json_object(text, pos)
    end
    if ch == "[" then
        return parse_json_array(text, pos)
    end
    if ch == "-" or ch:match("%d") then
        return parse_json_number(text, pos)
    end
    if text:sub(pos, pos + 3) == "true" then
        return true, pos + 4
    end
    if text:sub(pos, pos + 4) == "false" then
        return false, pos + 5
    end
    if text:sub(pos, pos + 3) == "null" then
        return nil, pos + 4
    end

    json_decode_error(text, pos, "unexpected token")
end

function JsonFallback.decode(text)
    local value, pos = parse_json_value(text, 1)
    pos = skip_whitespace(text, pos)
    if pos <= #text then
        json_decode_error(text, pos, "trailing data")
    end
    return value
end

local function resolve_json_module()
    local candidate = rawget(_G, "json")
    if type(candidate) == "table" and type(candidate.encode) == "function" and type(candidate.decode) == "function" then
        return candidate
    end

    candidate = rawget(_G, "JSON")
    if type(candidate) == "table" and type(candidate.encode) == "function" and type(candidate.decode) == "function" then
        return candidate
    end

    candidate = try_require("json")
    if type(candidate) == "table" and type(candidate.encode) == "function" and type(candidate.decode) == "function" then
        return candidate
    end

    return JsonFallback
end

local json = resolve_json_module()

function AgentEngine:log(msg)
    print("[AgentEngine] " .. tostring(msg))
end

function AgentEngine:log_once(key, msg)
    if self.logged_messages[key] then
        return
    end
    self.logged_messages[key] = true
    self:log(msg)
end

function AgentEngine:stringify_id(value)
    if value == nil then
        return nil
    end
    return tostring(value)
end

function AgentEngine:safe_get(t, k)
    if type(t) ~= "table" then
        return nil
    end
    return t[k]
end

function AgentEngine:normalize_string_field(value, depth)
    depth = depth or 0
    if value == nil or depth > 3 then
        return nil
    end

    local value_type = type(value)
    if value_type == "string" or value_type == "number" then
        local normalized = tostring(value)
        if normalized ~= "" then
            return normalized
        end
        return nil
    end
    if value_type ~= "table" then
        return nil
    end

    local direct_candidates = { "key", "deck_key", "slug", "id", "name", "label" }
    for _, key in ipairs(direct_candidates) do
        local normalized = self:normalize_string_field(self:safe_get(value, key), depth + 1)
        if normalized ~= nil then
            return normalized
        end
    end

    local nested_candidates = {
        self:safe_get(value, "center"),
        self:safe_get(value, "config"),
        self:safe_get(value, "effect"),
        self:safe_get(self:safe_get(value, "config"), "center"),
        self:safe_get(self:safe_get(value, "effect"), "center"),
        self:safe_get(self:safe_get(value, "ability"), "extra"),
    }
    for _, nested in ipairs(nested_candidates) do
        local normalized = self:normalize_string_field(nested, depth + 1)
        if normalized ~= nil then
            return normalized
        end
    end

    return nil
end

function AgentEngine:safe_serialize(value, depth)
    depth = depth or 0
    if depth > 3 then
        return nil
    end

    local value_type = type(value)
    if value_type == "number" or value_type == "string" or value_type == "boolean" then
        return value
    end
    if value_type ~= "table" then
        return nil
    end

    local is_array = true
    local max_index = 0
    for key, _ in pairs(value) do
        if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
            is_array = false
            break
        end
        if key > max_index then
            max_index = key
        end
    end

    local out = json_object({})
    if is_array then
        for i = 1, max_index do
            local serialized = self:safe_serialize(value[i], depth + 1)
            if serialized ~= nil then
                out = out or {}
                out[#out + 1] = serialized
            end
        end
        setmetatable(out, nil)
        return out
    end

    for key, inner_value in pairs(value) do
        if type(key) == "string" then
            local serialized = self:safe_serialize(inner_value, depth + 1)
            if serialized ~= nil then
                out[key] = serialized
            end
        end
    end
    return out
end

function AgentEngine:current_phase()
    if not G or not G.STATE or not G.STATES then
        return "UNKNOWN"
    end
    if G.STATE == G.STATES.SELECTING_HAND then return "SELECTING_HAND" end
    if G.STATES.BLIND_SELECT and G.STATE == G.STATES.BLIND_SELECT then return "BLIND_SELECT" end
    if G.STATES.ROUND_EVAL and G.STATE == G.STATES.ROUND_EVAL then return "ROUND_EVAL" end
    if G.STATES.SHOP and G.STATE == G.STATES.SHOP then return "SHOP" end
    if G.STATES.TAROT_PACK and G.STATE == G.STATES.TAROT_PACK then return "PACK_CHOICE" end
    if G.STATES.SPECTRAL_PACK and G.STATE == G.STATES.SPECTRAL_PACK then return "PACK_CHOICE" end
    if G.STATES.STANDARD_PACK and G.STATE == G.STATES.STANDARD_PACK then return "PACK_CHOICE" end
    if G.STATES.BUFFOON_PACK and G.STATE == G.STATES.BUFFOON_PACK then return "PACK_CHOICE" end
    if G.STATES.PLANET_PACK and G.STATE == G.STATES.PLANET_PACK then return "PACK_CHOICE" end
    return tostring(G.STATE)
end

function AgentEngine:current_pack_kind()
    if not G or not G.STATE or not G.STATES then
        return nil
    end
    if G.STATES.TAROT_PACK and G.STATE == G.STATES.TAROT_PACK then return "Arcana" end
    if G.STATES.SPECTRAL_PACK and G.STATE == G.STATES.SPECTRAL_PACK then return "Spectral" end
    if G.STATES.STANDARD_PACK and G.STATE == G.STATES.STANDARD_PACK then return "Standard" end
    if G.STATES.BUFFOON_PACK and G.STATE == G.STATES.BUFFOON_PACK then return "Buffoon" end
    if G.STATES.PLANET_PACK and G.STATE == G.STATES.PLANET_PACK then return "Celestial" end
    return nil
end

function AgentEngine:get_game()
    return self:safe_get(_G, "G") and G.GAME or nil
end

function AgentEngine:get_round_resets()
    return self:safe_get(self:get_game(), "round_resets")
end

function AgentEngine:get_current_round()
    return self:safe_get(self:get_game(), "current_round")
end

function AgentEngine:get_blind_states()
    return self:safe_get(self:get_round_resets(), "blind_states")
end

function AgentEngine:get_blind_state(slot)
    if type(slot) ~= "string" then
        return nil
    end
    return self:safe_get(self:get_blind_states(), slot)
end

function AgentEngine:get_blind_choices()
    return self:safe_get(self:get_round_resets(), "blind_choices")
end

function AgentEngine:resolve_blind_choice_slot()
    local game = self:get_game()
    local explicit_slot = self:safe_get(game, "blind_on_deck")
    local blind_choices = self:get_blind_choices()
    if type(explicit_slot) == "string" and self:safe_get(blind_choices, explicit_slot) ~= nil then
        return explicit_slot
    end

    local blind_states = self:get_blind_states()
    local ordered_slots = { "Small", "Big", "Boss" }
    for _, slot in ipairs(ordered_slots) do
        if self:safe_get(blind_states, slot) == "Select" and self:safe_get(blind_choices, slot) ~= nil then
            return slot
        end
    end

    for _, slot in ipairs(ordered_slots) do
        local blind_state = self:safe_get(blind_states, slot)
        if blind_state ~= "Defeated" and self:safe_get(blind_choices, slot) ~= nil then
            return slot
        end
    end

    if type(explicit_slot) == "string" and explicit_slot ~= "" then
        return explicit_slot
    end
    return nil
end

function AgentEngine:get_blind_choice_slot()
    return self:resolve_blind_choice_slot()
end

function AgentEngine:get_blind_choice_key(blind_slot)
    blind_slot = blind_slot or self:resolve_blind_choice_slot()
    local blind_choices = self:get_blind_choices()
    local blind_key = blind_slot and self:safe_get(blind_choices, blind_slot) or nil
    if type(blind_key) == "string" and blind_key ~= "" then
        return blind_key
    end
    return nil
end

function AgentEngine:get_blind_choice_ref(blind_slot)
    local blind_key = self:get_blind_choice_key(blind_slot)
    if blind_key and G and G.P_BLINDS then
        return G.P_BLINDS[blind_key]
    end
    return nil
end

function AgentEngine:get_blind_choice_uibox(blind_slot)
    blind_slot = blind_slot or self:resolve_blind_choice_slot()
    local blind_select_opts = self:safe_get(_G, "G") and self:safe_get(G, "blind_select_opts") or nil
    if type(blind_slot) == "string" and type(blind_select_opts) == "table" then
        return blind_select_opts[string.lower(blind_slot)]
    end
    return nil
end

function AgentEngine:get_blind_choice_button(blind_slot)
    local blind_ui = self:get_blind_choice_uibox(blind_slot)
    if not blind_ui or type(blind_ui.get_UIE_by_ID) ~= "function" then
        return nil
    end

    local ok, button = pcall(function()
        return blind_ui:get_UIE_by_ID("select_blind_button")
    end)
    if ok then
        return button
    end
    return nil
end

function AgentEngine:prime_blind_choice_button(blind_slot)
    local blind_ui = self:get_blind_choice_uibox(blind_slot)
    if not blind_ui or type(blind_ui.get_UIE_by_ID) ~= "function" then
        return nil
    end
    if not G or not G.FUNCS or type(G.FUNCS.blind_choice_handler) ~= "function" then
        return self:get_blind_choice_button(blind_slot)
    end

    local ok_node, choice_node = pcall(function()
        return blind_ui:get_UIE_by_ID(blind_slot)
    end)
    if ok_node and choice_node then
        pcall(function()
            G.FUNCS.blind_choice_handler(choice_node)
        end)
    end

    return self:get_blind_choice_button(blind_slot)
end

function AgentEngine:get_visible_blind_target_score(phase, visible_blind)
    phase = phase or self:current_phase()
    visible_blind = visible_blind or self:get_visible_blind_ref(phase)

    local explicit_target = tonumber(self:safe_get(visible_blind, "chips")) or 0
    if explicit_target > 0 then
        return explicit_target
    end

    if phase == "BLIND_SELECT" and visible_blind and type(get_blind_amount) == "function" then
        local round_resets = self:get_round_resets()
        local game = self:get_game()
        local blind_ante = tonumber(self:safe_get(round_resets, "blind_ante")) or tonumber(self:safe_get(round_resets, "ante")) or 1
        local blind_mult = tonumber(self:safe_get(visible_blind, "mult")) or 0
        local ante_scaling = tonumber(self:safe_get(self:safe_get(game, "starting_params"), "ante_scaling")) or 1
        local ok_target, blind_target = pcall(function()
            return get_blind_amount(blind_ante) * blind_mult * ante_scaling
        end)
        if ok_target and tonumber(blind_target) then
            return tonumber(blind_target)
        end
    end

    return 0
end

function AgentEngine:get_visible_blind_ref(phase)
    local game = self:get_game()
    local active_blind = self:safe_get(game, "blind")
    phase = phase or self:current_phase()

    if phase == "BLIND_SELECT" then
        local blind_choice_ref = self:get_blind_choice_ref()
        if blind_choice_ref then
            return blind_choice_ref
        end
    end

    if active_blind then
        local blind_name = self:safe_get(active_blind, "name")
        local blind_chips = self:safe_get(active_blind, "chips") or 0
        if blind_chips > 0 or (type(blind_name) == "string" and blind_name ~= "") then
            return active_blind
        end
    end

    return self:get_blind_choice_ref()
end

function AgentEngine:get_round_eval_cashout_button()
    if not G or not G.round_eval then
        return nil
    end
    if type(G.round_eval.get_UIE_by_ID) ~= "function" then
        return nil
    end

    local ok, button = pcall(function()
        return G.round_eval:get_UIE_by_ID("cash_out_button")
    end)
    if ok then
        return button
    end
    return nil
end

function AgentEngine:find_button_in_tree(root, button_names)
    if not root then
        return nil
    end

    local wanted = {}
    if type(button_names) == "table" then
        for _, name in ipairs(button_names) do
            wanted[name] = true
        end
    elseif type(button_names) == "string" and button_names ~= "" then
        wanted[button_names] = true
    end

    local function search_node(node)
        if type(node) ~= "table" then
            return nil
        end

        local config = node.config
        if type(config) == "table" and wanted[config.button] then
            return node
        end

        local children = node.children
        if type(children) == "table" then
            for _, child in pairs(children) do
                local found = search_node(child)
                if found then
                    return found
                end

                local child_config = self:safe_get(child, "config")
                local child_object = self:safe_get(child_config, "object")
                local child_root = self:safe_get(child_object, "UIRoot")
                if child_root then
                    found = search_node(child_root)
                    if found then
                        return found
                    end
                end
            end
        end

        return nil
    end

    local root_node = self:safe_get(root, "UIRoot") or root
    return search_node(root_node)
end

function AgentEngine:get_shop_next_round_button()
    if not G or not G.shop or type(G.shop.get_UIE_by_ID) ~= "function" then
        return nil
    end

    local ok, button = pcall(function()
        return G.shop:get_UIE_by_ID("next_round_button")
    end)
    if ok then
        return button
    end
    return nil
end

function AgentEngine:get_shop_reroll_button()
    if not G or not G.shop then
        return nil
    end
    return self:find_button_in_tree(G.shop, "reroll_shop")
end

function AgentEngine:get_blind_skip_button(blind_slot)
    local blind_ui = self:get_blind_choice_uibox(blind_slot)
    if not blind_ui then
        return nil
    end
    return self:find_button_in_tree(blind_ui, "skip_blind")
end

function AgentEngine:ensure_card_focus_ui(card)
    if type(card) ~= "table" then
        return nil
    end

    local focused_ui = self:safe_get(self:safe_get(card, "children"), "focused_ui")
    if focused_ui then
        return focused_ui
    end

    local focus_state = self:safe_get(self:safe_get(card, "states"), "focus")
    if type(focus_state) == "table" then
        focus_state.is = true
    end

    pcall(function()
        if type(card.hover) == "function" then
            card:hover()
        end
    end)

    return self:safe_get(self:safe_get(card, "children"), "focused_ui")
end

function AgentEngine:get_shop_item_button(card)
    local focused_ui = self:ensure_card_focus_ui(card)
    if not focused_ui then
        return nil
    end

    local button_names = { "buy_from_shop", "use_card" }
    return self:find_button_in_tree(focused_ui, button_names)
end

function AgentEngine:is_round_eval_ready()
    return self:get_round_eval_cashout_button() ~= nil
end

function AgentEngine:is_shop_ready()
    local game = self:get_game()
    return G.shop ~= nil
        and (self:safe_get(game, "chips") or 0) == 0
        and self:get_shop_next_round_button() ~= nil
        and self:shop_item_count() > 0
end

function AgentEngine:is_input_locked()
    if not G then
        return true
    end
    local controller = self:safe_get(G, "CONTROLLER")
    if self:safe_get(controller, "lock_input") then
        return true
    end
    if self:safe_get(self:safe_get(controller, "locks"), "load") then
        return true
    end
    if self:safe_get(self:safe_get(G, "SETTINGS"), "paused") then
        return true
    end
    if self:safe_get(G, "screenwipe") then
        return true
    end
    return false
end

function AgentEngine:is_state_settled()
    return G ~= nil and G.STATE_COMPLETE == true and not self:is_input_locked()
end

function AgentEngine:count_cards(cardarea)
    local cards = self:safe_get(cardarea, "cards")
    if type(cards) ~= "table" then
        return 0
    end
    return #cards
end

function AgentEngine:find_named_table(root, wanted_key, max_depth, seen)
    if type(root) ~= "table" or max_depth < 0 then
        return nil
    end
    seen = seen or {}
    if seen[root] then
        return nil
    end
    seen[root] = true

    local direct = self:safe_get(root, wanted_key)
    if type(direct) == "table" and type(self:safe_get(direct, "cards")) == "table" then
        return direct
    end

    if max_depth == 0 then
        return nil
    end

    for _, value in pairs(root) do
        if type(value) == "table" then
            local found = self:find_named_table(value, wanted_key, max_depth - 1, seen)
            if found then
                return found
            end
        end
    end
    return nil
end

function AgentEngine:get_pack_card_area()
    if not G then
        return nil
    end
    if type(self:safe_get(G, "pack_cards")) == "table" and type(self:safe_get(G.pack_cards, "cards")) == "table" then
        return G.pack_cards
    end
    return self:find_named_table(G, "pack_cards", 4)
end

function AgentEngine:get_pack_cards()
    local area = self:get_pack_card_area()
    local cards = self:safe_get(area, "cards")
    if type(cards) == "table" then
        return cards
    end
    return {}
end

function AgentEngine:pack_item_count()
    return #self:get_pack_cards()
end

function AgentEngine:shop_item_count()
    return self:count_cards(G and G.shop_jokers)
        + self:count_cards(G and G.shop_vouchers)
        + self:count_cards(G and G.shop_booster)
end

function AgentEngine:flow_token()
    local game = self:get_game()
    local current_round = self:get_current_round()
    local blind_slot = self:resolve_blind_choice_slot()
    local visible_blind = self:get_visible_blind_ref()
    local blind_states = self:get_blind_states() or {}
    local token = json_object({
        phase = self:current_phase(),
        raw_state = G and tostring(G.STATE) or "UNKNOWN",
        state_complete = G and G.STATE_COMPLETE == true or false,
        input_locked = self:is_input_locked(),
        blind_slot = blind_slot,
        blind_key = self:get_blind_choice_key(blind_slot),
        blind_name = self:safe_get(visible_blind, "name") or "",
        blind_target = self:get_visible_blind_target_score(self:current_phase(), visible_blind),
        current_score = self:safe_get(game, "chips") or 0,
        hands_left = self:safe_get(current_round, "hands_left") or 0,
        discards_left = self:safe_get(current_round, "discards_left") or 0,
        money = self:safe_get(game, "dollars") or 0,
        hand_count = self:count_cards(G and G.hand),
        deck_count = self:count_cards(G and G.deck),
        discard_count = self:count_cards(G and G.discard),
        shop_item_count = self:shop_item_count(),
        pack_kind = self:current_pack_kind() or "",
        pack_item_count = self:pack_item_count(),
        consumable_count = self:count_cards(G and G.consumeables),
        blind_ui_ready = self:get_blind_choice_uibox(blind_slot) ~= nil,
        blind_small_state = self:safe_get(blind_states, "Small") or "",
        blind_big_state = self:safe_get(blind_states, "Big") or "",
        blind_boss_state = self:safe_get(blind_states, "Boss") or ""
    })

    local ok, encoded = pcall(function()
        return JsonFallback.encode(token)
    end)
    if ok and type(encoded) == "string" then
        return encoded
    end
    return tostring(G and G.STATE or "UNKNOWN")
end

function AgentEngine:is_pending_transition_resolved()
    local pending = self.pending_transition
    if not pending then
        return true
    end

    local phase = self:current_phase()
    if pending.action == "SELECT_BLIND" then
        if phase ~= "BLIND_SELECT" then
            return true
        end
        if G.blind_select == nil then
            return true
        end
        if pending.blind_slot and self:get_blind_state(pending.blind_slot) ~= "Select" then
            return true
        end
        return false
    elseif pending.action == "SKIP" then
        if phase ~= "BLIND_SELECT" then
            return true
        end
        if pending.blind_slot and self:get_blind_state(pending.blind_slot) ~= "Select" then
            return true
        end
        return false
    elseif pending.action == "CASH_OUT" then
        if phase ~= "ROUND_EVAL" then
            return true
        end
        if G.round_eval == nil then
            return true
        end
        return false
    elseif pending.action == "NEXT_ROUND" then
        if phase ~= "SHOP" then
            return true
        end
        if G.shop == nil then
            return true
        end
        return false
    elseif pending.action == "TAKE_PACK_CARD" then
        if phase ~= "PACK_CHOICE" then
            return true
        end
        if self:pack_item_count() <= 0 then
            return true
        end
        return false
    elseif pending.phase and phase ~= pending.phase then
        return true
    end

    return self:flow_token() ~= pending.flow_token
end

function AgentEngine:await_pending_transition()
    if not self.pending_transition then
        return false
    end

    if self:is_pending_transition_resolved() then
        self.pending_transition = nil
        return false
    end

    self.pending_transition.stalled_polls = (self.pending_transition.stalled_polls or 0) + 1
    if self.pending_transition.stalled_polls >= self.pending_transition_max_polls then
        self:log("Pending transition stalled for action " .. tostring(self.pending_transition.action) .. "; clearing wait state.")
        self.pending_transition = nil
        self.last_request_fingerprint = nil
        self.last_response_action = nil
        return false
    end

    return true
end

function AgentEngine:is_phase_ready(phase)
    if not self:is_state_settled() then
        return false
    end
    if phase == "SELECTING_HAND" then
        return G.hand and type(G.hand.cards) == "table" and #G.hand.cards > 0
    end
    if phase == "BLIND_SELECT" then
        local blind_slot = self:resolve_blind_choice_slot()
        local blind_ui = self:get_blind_choice_uibox(blind_slot)
        local blind_button = self:get_blind_choice_button(blind_slot)
        return G
            and G.blind_select ~= nil
            and blind_ui ~= nil
            and blind_button ~= nil
            and blind_slot ~= nil
            and self:get_blind_state(blind_slot) == "Select"
            and self:get_blind_choice_ref(blind_slot) ~= nil
    end
    if phase == "ROUND_EVAL" then
        return self:is_round_eval_ready()
    end
    if phase == "SHOP" then
        return self:is_shop_ready()
    end
    if phase == "PACK_CHOICE" then
        return self:pack_item_count() > 0
    end
    return true
end

function AgentEngine:serialize_card(card, fallback_id)
    if not card then
        return nil
    end
    return {
        id = self:stringify_id(card.unique_val or fallback_id),
        rank = self:safe_get(card.base, "value") or "2",
        suit = self:safe_get(card.base, "suit") or "Spades",
        base_chips = self:safe_get(card.base, "nominal") or 0,
        enhancement = self:safe_get(card.ability, "effect") or "None",
        edition = self:safe_get(card.edition, "type") or "None",
        seal = card.seal or "None",
        is_debuffed = card.debuff or false
    }
end

function AgentEngine:serialize_joker(joker, fallback_id)
    if not joker then
        return nil
    end
    return {
        id = self:stringify_id(joker.unique_val or fallback_id),
        name = self:safe_get(joker.ability, "name") or "Unknown",
        edition = self:safe_get(joker.edition, "type") or "None",
        sell_value = joker.sell_cost or 0,
        is_debuffed = joker.debuff or false,
        is_eternal = self:safe_get(joker.ability, "eternal") or false,
        is_perishable = self:safe_get(joker.ability, "perishable") or false,
        is_rental = self:safe_get(joker.ability, "rental") or false,
        internal_state = self:safe_serialize(joker.ability)
    }
end

function AgentEngine:serialize_shop_item(card, fallback_id)
    if not card then
        return nil
    end
    local item_name = self:safe_get(card.ability, "name")
    local item_rank = self:safe_get(card.base, "value")
    local item_suit = self:safe_get(card.base, "suit")
    if item_name == nil and item_rank ~= nil and item_suit ~= nil then
        item_name = tostring(item_rank) .. " of " .. tostring(item_suit)
    end
    return {
        id = self:stringify_id(card.unique_val or fallback_id),
        name = item_name or "Unknown",
        set = self:safe_get(card.ability, "set") or (item_rank and "PlayingCard") or "Unknown",
        cost = card.cost or 0,
        edition = self:safe_get(card.edition, "type") or "None",
        rank = item_rank,
        suit = item_suit,
        base_chips = self:safe_get(card.base, "nominal"),
        enhancement = self:safe_get(card.ability, "effect") or "None",
        seal = card.seal or "None",
        is_debuffed = card.debuff or false,
        is_eternal = self:safe_get(card.ability, "eternal") or false,
        is_perishable = self:safe_get(card.ability, "perishable") or false,
        is_rental = self:safe_get(card.ability, "rental") or false,
        metadata = self:safe_serialize(card.ability)
    }
end

function AgentEngine:serialize_state()
    local game = self:get_game()
    local current_round = self:get_current_round()
    local round_resets = self:get_round_resets()
    local phase = self:current_phase()
    local blind_slot = self:resolve_blind_choice_slot()
    local visible_blind = self:get_visible_blind_ref(phase)
    local visible_blind_target = self:get_visible_blind_target_score(phase, visible_blind)

    local state = json_object({
        meta = json_object({
            protocol_version = self.protocol_version,
            seed = self:safe_get(self:safe_get(game, "pseudorandom"), "seed") or "UNKNOWN",
            ante = self:safe_get(round_resets, "ante") or 1,
            round = self:safe_get(round_resets, "round") or 1,
            phase = phase,
            stake = self:safe_get(game, "stake") or 1,
            blind_on_deck = blind_slot,
            deck_name = self:normalize_string_field(self:safe_get(game, "selected_back")) or self:safe_get(self:safe_get(game, "selected_back"), "name"),
            deck_key = self:normalize_string_field(self:safe_get(game, "selected_back_key")) or self:normalize_string_field(self:safe_get(game, "selected_back")),
            no_interest = self:safe_get(self:safe_get(game, "modifiers"), "no_interest") or self:safe_get(self:safe_get(game, "starting_params"), "no_interest") or false,
            pack_kind = self:current_pack_kind(),
            stage = G and tostring(G.STAGE) or "UNKNOWN",
            state_complete = G and G.STATE_COMPLETE == true or false,
            input_locked = self:is_input_locked()
        }),
        blind = json_object({
            name = self:safe_get(visible_blind, "name") or "Unknown",
            target_score = visible_blind_target,
            current_score = self:safe_get(game, "chips") or 0,
            boss_modifier = self:safe_get(self:safe_get(self:safe_get(self:safe_get(visible_blind, "config"), "blind"), "boss"), "name"),
            is_boss = (blind_slot == "Boss")
        }),
        economy = json_object({
            money = self:safe_get(game, "dollars") or 0,
            hands_left = self:safe_get(current_round, "hands_left") or 0,
            discards_left = self:safe_get(current_round, "discards_left") or 0,
            hand_size = self:safe_get(G.hand and G.hand.config, "card_limit") or 8,
            joker_slots = self:safe_get(G.jokers and G.jokers.config, "card_limit") or 5,
            consumable_slots = self:safe_get(G.consumeables and G.consumeables.config, "card_limit") or 2,
            reroll_cost = self:safe_get(current_round, "reroll_cost") or 5,
            interest_cap = self:safe_get(game, "interest_cap") or 25,
            interest_amount = self:safe_get(game, "interest_amount") or 1
        }),
        hand = {},
        jokers = {},
        deck = {},
        discard_pile = {},
        consumables = {},
        hand_levels = json_object({}),
        blind_choices = json_object({}),
        shop_items = {},
        pack_items = {}
    })

    if G.hand and G.hand.cards then
        for i, card in ipairs(G.hand.cards) do
            table.insert(state.hand, self:serialize_card(card, "H_" .. tostring(i)))
        end
    end

    if G.jokers and G.jokers.cards then
        for i, joker in ipairs(G.jokers.cards) do
            table.insert(state.jokers, self:serialize_joker(joker, "J_" .. tostring(i)))
        end
    end

    if G.deck and G.deck.cards then
        for i, card in ipairs(G.deck.cards) do
            table.insert(state.deck, self:serialize_card(card, "D_" .. tostring(i)))
        end
    end

    if G.discard and G.discard.cards then
        for i, card in ipairs(G.discard.cards) do
            table.insert(state.discard_pile, self:serialize_card(card, "X_" .. tostring(i)))
        end
    end

    if G.consumeables and G.consumeables.cards then
        for i, consumable in ipairs(G.consumeables.cards) do
            table.insert(state.consumables, self:serialize_shop_item(consumable, "CNS_" .. tostring(i)))
        end
    end

    if game and game.hands then
        for hand_name, hand_state in pairs(game.hands) do
            state.hand_levels[hand_name] = json_object({
                level = self:safe_get(hand_state, "level") or 1,
                planets = self:safe_get(hand_state, "planet") or self:safe_get(hand_state, "planets") or 0,
                played = self:safe_get(hand_state, "played") or 0,
                played_this_round = self:safe_get(hand_state, "played_this_round") or 0,
                chips = self:safe_get(hand_state, "chips"),
                mult = self:safe_get(hand_state, "mult")
            })
        end
    end

    if type(self:get_blind_choices()) == "table" then
        for blind_name, blind_key in pairs(self:get_blind_choices()) do
            if type(blind_name) == "string" and blind_key ~= nil then
                state.blind_choices[blind_name] = tostring(blind_key)
            end
        end
    end

    if phase == "SHOP" then
        local areas = {
            { prefix = "SJ", zone = G.shop_jokers },
            { prefix = "SV", zone = G.shop_vouchers },
            { prefix = "SB", zone = G.shop_booster }
        }
        for _, area in ipairs(areas) do
            if area.zone and area.zone.cards then
                for i, item in ipairs(area.zone.cards) do
                    table.insert(state.shop_items, self:serialize_shop_item(item, area.prefix .. "_" .. tostring(i)))
                end
            end
        end
    end

    if phase == "PACK_CHOICE" then
        local pack_cards = self:get_pack_cards()
        for i, item in ipairs(pack_cards) do
            table.insert(state.pack_items, self:serialize_shop_item(item, "PK_" .. tostring(i)))
        end
    end

    local ok, encoded = pcall(function()
        return JsonFallback.encode(state)
    end)
    if ok and type(encoded) == "string" then
        return encoded
    end

    self:log("State serialization failed: " .. tostring(encoded))
    return "{}"
end

function AgentEngine:find_hand_cards(card_ids)
    local target_cards = {}
    if not G.hand or type(G.hand.cards) ~= "table" then
        return target_cards
    end
    if type(card_ids) ~= "table" then
        return target_cards
    end

    for _, target_id in ipairs(card_ids) do
        local wanted = self:stringify_id(target_id)
        for i, card in ipairs(G.hand.cards) do
            local card_id = self:stringify_id(card.unique_val or ("H_" .. tostring(i)))
            if card_id == wanted then
                table.insert(target_cards, card)
                break
            end
        end
    end
    return target_cards
end

function AgentEngine:find_shop_item(target_id)
    local wanted = self:stringify_id(target_id)
    local areas = {
        { prefix = "SJ_", zone = G.shop_jokers },
        { prefix = "SV_", zone = G.shop_vouchers },
        { prefix = "SB_", zone = G.shop_booster }
    }
    for _, area in ipairs(areas) do
        if area.zone and area.zone.cards then
            for i, item in ipairs(area.zone.cards) do
                local item_id = self:stringify_id(item.unique_val or (area.prefix .. tostring(i)))
                if item_id == wanted then
                    return item
                end
            end
        end
    end
    return nil
end

function AgentEngine:find_pack_item(target_id)
    local wanted = self:stringify_id(target_id)
    local pack_cards = self:get_pack_cards()
    for i, item in ipairs(pack_cards) do
        local item_id = self:stringify_id(item.unique_val or ("PK_" .. tostring(i)))
        if item_id == wanted then
            return item
        end
    end
    return nil
end

function AgentEngine:execute_action(action_json)
    local success, action = pcall(function()
        return json.decode(action_json)
    end)
    if not success or type(action) ~= "table" then
        self:log("Invalid JSON action payload: " .. tostring(action))
        action = { action = "ERROR", message = "Invalid JSON action" }
    end

    if action.action == "ERROR" then
        self:log("Server returned ERROR: " .. tostring(action.message))
        return "ERROR"
    end

    if action.action == "NO_OP" then
        return "NO_OP", tostring(action.message or "")
    end

    self:log("Executing Action: " .. tostring(action.action))

    if action.action == "SELECT_BLIND" then
        local blind_slot = self:resolve_blind_choice_slot()
        local blind_key = self:get_blind_choice_key(blind_slot)
        local blind_ref = self:get_blind_choice_ref(blind_slot)
        local blind_ui = self:get_blind_choice_uibox(blind_slot)
        local blind_button = self:prime_blind_choice_button(blind_slot)
        if G.GAME and blind_slot and blind_ref and blind_ui and blind_button and G.blind_select and self:get_blind_state(blind_slot) == "Select" then
            G.GAME.blind_on_deck = blind_slot
            local ok_select, select_err = pcall(function()
                blind_button:click()
            end)
            if ok_select then
                return action.action, nil
            end
            self:log("Blind selection failed: " .. tostring(select_err))
        else
            self:log("Blind selection skipped: UI is not ready for " .. tostring(blind_key or blind_slot or "unknown"))
        end
        return "NO_OP", nil
    end

    if action.action == "SKIP" then
        local blind_slot = self:resolve_blind_choice_slot()
        local skip_button = self:get_blind_skip_button(blind_slot)
        if skip_button then
            local ok_skip, skip_err = pcall(function()
                skip_button:click()
            end)
            if ok_skip then
                return action.action, nil
            end
            self:log("Blind skip failed: " .. tostring(skip_err))
        end
        return "NO_OP", nil
    end

    if action.action == "CASH_OUT" then
        local cash_out_button = self:get_round_eval_cashout_button()
        if cash_out_button then
            local ok_cash_out, cash_out_err = pcall(function()
                cash_out_button:click()
            end)
            if ok_cash_out then
                return action.action, nil
            end
            self:log("Cash out failed: " .. tostring(cash_out_err))
        else
            self:log("Cash out skipped: round eval UI is not ready.")
        end
        return "NO_OP", nil
    end

    if action.action == "REROLL_SHOP" then
        local reroll_button = self:get_shop_reroll_button()
        if reroll_button then
            local ok_reroll, reroll_err = pcall(function()
                reroll_button:click()
            end)
            if ok_reroll then
                return action.action, nil
            end
            self:log("Shop reroll failed: " .. tostring(reroll_err))
        end
        return "NO_OP", nil
    end

    if action.action == "NEXT_ROUND" then
        local next_round_button = self:get_shop_next_round_button()
        if next_round_button then
            local ok_next_round, next_round_err = pcall(function()
                next_round_button:click()
            end)
            if ok_next_round then
                return action.action, nil
            end
            self:log("Next round transition failed: " .. tostring(next_round_err))
        end
        return "NO_OP", nil
    end

    if action.action == "BUY_CARD" then
        local target = self:find_shop_item(action.target_id)
        local buy_button = self:get_shop_item_button(target)
        if target and buy_button then
            local ok_buy, buy_err = pcall(function()
                buy_button:click()
            end)
            if ok_buy then
                return action.action, nil
            end
            self:log("Buy from shop failed: " .. tostring(buy_err))
        else
            self:log("Failed to buy shop item: " .. tostring(action.target_id))
        end
        return "NO_OP", nil
    end

    if action.action == "TAKE_PACK_CARD" then
        local target = self:find_pack_item(action.target_id)
        local use_button = self:get_shop_item_button(target)
        if target and use_button then
            local ok_use, use_err = pcall(function()
                use_button:click()
            end)
            if ok_use then
                return action.action, nil
            end
            self:log("Pack selection failed: " .. tostring(use_err))
        else
            self:log("Failed to select pack item: " .. tostring(action.target_id))
        end
        return "NO_OP", nil
    end

    if not G.hand or type(G.hand.cards) ~= "table" then
        return "NO_OP", nil
    end

    if G.hand.highlighted and type(G.hand.highlighted) == "table" then
        for i = #G.hand.highlighted, 1, -1 do
            G.hand:remove_from_highlighted(G.hand.highlighted[i])
        end
    end

    local target_cards = self:find_hand_cards(action.cards)
    for _, card in ipairs(target_cards) do
        G.hand:add_to_highlighted(card)
    end

    if action.action == "PLAY_HAND" then
        if G.hand.highlighted and #G.hand.highlighted > 0 and G.FUNCS and G.FUNCS.play_cards_from_highlighted then
            local ok_play, play_err = pcall(function()
                G.FUNCS.play_cards_from_highlighted()
            end)
            if ok_play then
                return action.action, nil
            end
            self:log("Failed to play highlighted cards: " .. tostring(play_err))
        else
            self:log("Failed to play: no valid cards highlighted.")
        end
        return "NO_OP", nil
    elseif action.action == "DISCARD" then
        if G.hand.highlighted and #G.hand.highlighted > 0 and G.FUNCS and G.FUNCS.discard_cards_from_highlighted then
            local ok_discard, discard_err = pcall(function()
                G.FUNCS.discard_cards_from_highlighted()
            end)
            if ok_discard then
                return action.action, nil
            end
            self:log("Failed to discard highlighted cards: " .. tostring(discard_err))
        else
            self:log("Failed to discard: no valid cards highlighted.")
        end
        return "NO_OP", nil
    end

    return "NO_OP", nil
end

function AgentEngine:_tick_impl()
    if not G or not G.STATE or not G.STATES then
        return
    end

    if self:await_pending_transition() then
        return
    end

    local phase = self:current_phase()
    if phase ~= "SELECTING_HAND" and phase ~= "BLIND_SELECT" and phase ~= "ROUND_EVAL" and phase ~= "SHOP" and phase ~= "PACK_CHOICE" then
        self.noop_waiting = false
        self.noop_wait_fingerprint = nil
        self.noop_poll_counter = 0
        return
    end
    if not self:is_phase_ready(phase) then
        return
    end

    local current_round = self:safe_get(self:safe_get(G, "GAME"), "current_round")
    local blind = self:safe_get(self:safe_get(G, "GAME"), "blind")
    local boss = self:safe_get(blind, "boss")
    if boss and self:safe_get(boss, "name") == "The Needle" and self:safe_get(current_round, "hands_left") == 0 then
        return
    end

    if not socket or type(socket.tcp) ~= "function" then
        self:log_once("missing_socket", "LuaSocket module 'socket' is unavailable; the agent cannot connect to the Python server.")
        return
    end

    local state_json = self:serialize_state()
    local fingerprint = phase .. "::" .. state_json
    if phase ~= "SELECTING_HAND" or self.noop_wait_fingerprint ~= fingerprint then
        self.noop_waiting = false
        self.noop_wait_fingerprint = nil
        self.noop_poll_counter = 0
    end
    if self.last_request_fingerprint == fingerprint then
        if phase ~= "SELECTING_HAND" then
            return
        end
        if self.noop_waiting then
            self.noop_poll_counter = (self.noop_poll_counter or 0) + 1
            if self.noop_poll_counter < self.noop_poll_stride then
                return
            end
            self.noop_poll_counter = 0
        elseif self.last_response_action ~= "NO_OP" then
            return
        end
    end

    self.is_busy = true
    local tcp = socket.tcp()
    if not tcp then
        self:log("Failed to create TCP socket.")
        self.is_busy = false
        return
    end

    tcp:settimeout(self.socket_timeout_sec)
    local connected, err = tcp:connect(self.host, self.port)
    local executed_action = "NO_OP"
    local response_message = nil
    local flow_token_before = self:flow_token()
    if connected then
        local send_ok, send_err = tcp:send(state_json .. "\n")
        if not send_ok then
            self:log("Failed to send state to server: " .. tostring(send_err))
        else
            local response, _, partial = tcp:receive("*l")
            if response and response ~= "" then
                executed_action, response_message = self:execute_action(response)
                executed_action = executed_action or "NO_OP"
            elseif partial and partial ~= "" then
                executed_action, response_message = self:execute_action(partial)
                executed_action = executed_action or "NO_OP"
            else
                self:log("No response received from server.")
            end
        end
        pcall(function()
            tcp:close()
        end)
    else
        self:log("Connection failed: " .. tostring(err) .. ". Falling back to manual play.")
        pcall(function()
            tcp:close()
        end)
    end

    self.last_request_fingerprint = fingerprint
    self.last_response_action = executed_action
    self.last_response_message = response_message

    if phase == "SELECTING_HAND" and executed_action == "NO_OP" then
        local waiting_messages = {
            planning_started = true,
            planning_pending = true,
            planner_busy = true
        }
        self.noop_waiting = waiting_messages[tostring(response_message or "")] == true
        if self.noop_waiting then
            self.noop_wait_fingerprint = fingerprint
            self.noop_poll_counter = 0
        end
    else
        self.noop_waiting = false
        self.noop_wait_fingerprint = nil
        self.noop_poll_counter = 0
    end

    if executed_action ~= "NO_OP" and executed_action ~= "ERROR" then
        self.pending_transition = {
            action = executed_action,
            phase = phase,
            blind_slot = self:resolve_blind_choice_slot(),
            flow_token = flow_token_before,
            stalled_polls = 0
        }
    else
        self.pending_transition = nil
    end

    self.is_busy = false
end

function AgentEngine:tick()
    local ok, err = pcall(function()
        self:_tick_impl()
    end)
    if not ok then
        self.is_busy = false
        self:log("Tick error: " .. tostring(err))
    end
end

function AgentEngine:install_update_hook()
    if self.game_update_wrapped then
        return
    end
    if type(Game) ~= "table" or type(Game.update) ~= "function" then
        self:log_once("missing_game_update", "Game.update is unavailable; the agent tick hook could not be installed.")
        return
    end
    if Game.__agent_engine_wrapped then
        self.game_update_wrapped = true
        return
    end

    local original_update = Game.update
    Game.update = function(game_self, dt)
        local result = original_update(game_self, dt)
        if AgentEngine and not AgentEngine.is_busy then
            AgentEngine:tick()
        end
        return result
    end

    Game.__agent_engine_wrapped = true
    self.game_update_wrapped = true
end

AgentEngine:install_update_hook()

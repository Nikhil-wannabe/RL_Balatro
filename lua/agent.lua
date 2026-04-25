AgentEngine = AgentEngine or {
    is_busy = false,
    host = "127.0.0.1",
    port = 12345,
    timeout_sec = 2.0,
    protocol_version = "1.0.0"
}

local socket = require("socket")

function AgentEngine:log(msg)
    print("[AgentEngine] " .. tostring(msg))
end

function AgentEngine:safe_get(t, k)
    return t and t[k]
end

function AgentEngine:safe_serialize(value, depth)
    depth = depth or 0
    if depth > 3 then return nil end

    local value_type = type(value)
    if value_type == "number" or value_type == "string" or value_type == "boolean" then
        return value
    end
    if value_type ~= "table" then
        return nil
    end

    local out = {}
    for k, v in pairs(value) do
        if type(k) == "string" then
            local serialized = self:safe_serialize(v, depth + 1)
            if serialized ~= nil then
                out[k] = serialized
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
    return tostring(G.STATE)
end

function AgentEngine:serialize_card(card, fallback_id)
    if not card then return nil end
    return {
        id = card.unique_val or fallback_id,
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
    if not joker then return nil end
    return {
        id = joker.unique_val or fallback_id,
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
    if not card then return nil end
    return {
        id = card.unique_val or fallback_id,
        name = self:safe_get(card.ability, "name") or "Unknown",
        set = self:safe_get(card.ability, "set") or "Unknown",
        cost = card.cost or 0,
        edition = self:safe_get(card.edition, "type") or "None",
        is_eternal = self:safe_get(card.ability, "eternal") or false,
        is_perishable = self:safe_get(card.ability, "perishable") or false,
        is_rental = self:safe_get(card.ability, "rental") or false,
        metadata = self:safe_serialize(card.ability)
    }
end

function AgentEngine:serialize_state()
    local phase = self:current_phase()
    local state = {
        meta = {
            protocol_version = self.protocol_version,
            seed = self:safe_get(G.GAME.pseudorandom, "seed") or "UNKNOWN",
            ante = self:safe_get(G.GAME.round_resets, "ante") or 1,
            round = self:safe_get(G.GAME.round_resets, "round") or 1,
            phase = phase,
            stake = self:safe_get(G.GAME, "stake") or 1,
            blind_on_deck = self:safe_get(G.GAME, "blind_on_deck"),
            deck_name = self:safe_get(self:safe_get(G.GAME, "selected_back"), "name")
        },
        blind = {
            name = self:safe_get(G.GAME.blind, "name") or "Unknown",
            target_score = self:safe_get(G.GAME.blind, "chips") or 0,
            current_score = G.GAME.chips or 0,
            boss_modifier = self:safe_get(self:safe_get(self:safe_get(self:safe_get(G.GAME.blind, "config"), "blind"), "boss"), "name"),
            is_boss = (self:safe_get(G.GAME, "blind_on_deck") == "Boss")
        },
        economy = {
            money = G.GAME.dollars or 0,
            hands_left = self:safe_get(G.GAME.current_round, "hands_left") or 0,
            discards_left = self:safe_get(G.GAME.current_round, "discards_left") or 0,
            hand_size = self:safe_get(G.hand and G.hand.config, "card_limit") or 8,
            reroll_cost = self:safe_get(G.GAME.current_round, "reroll_cost") or 5,
            interest_cap = self:safe_get(G.GAME, "interest_cap") or 25,
            interest_amount = self:safe_get(G.GAME, "interest_amount") or 1
        },
        hand = {},
        jokers = {},
        deck = {},
        discard_pile = {},
        hand_levels = {},
        blind_choices = {},
        shop_items = {}
    }

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

    if G.GAME and G.GAME.hands then
        for hand_name, hand_state in pairs(G.GAME.hands) do
            state.hand_levels[hand_name] = {
                level = self:safe_get(hand_state, "level") or 1,
                planets = self:safe_get(hand_state, "planet") or self:safe_get(hand_state, "planets") or 0,
                played = self:safe_get(hand_state, "played") or 0,
                played_this_round = self:safe_get(hand_state, "played_this_round") or 0,
                chips = self:safe_get(hand_state, "chips"),
                mult = self:safe_get(hand_state, "mult")
            }
        end
    end

    if phase == "SHOP" then
        local areas = {
            {prefix = "SJ", zone = G.shop_jokers},
            {prefix = "SV", zone = G.shop_vouchers},
            {prefix = "SB", zone = G.shop_booster}
        }
        for _, area in ipairs(areas) do
            if area.zone and area.zone.cards then
                for i, item in ipairs(area.zone.cards) do
                    table.insert(state.shop_items, self:serialize_shop_item(item, area.prefix .. "_" .. tostring(i)))
                end
            end
        end
    end

    return json and json.encode(state) or "{}"
end

function AgentEngine:find_hand_cards(card_ids)
    local target_cards = {}
    if not G.hand or type(G.hand.cards) ~= "table" then return target_cards end

    if card_ids and type(card_ids) == "table" then
        for _, target_id in ipairs(card_ids) do
            for _, card in ipairs(G.hand.cards) do
                local card_id = card.unique_val
                if not card_id then
                    for i, c in ipairs(G.hand.cards) do
                        if "H_" .. tostring(i) == target_id and card == c then
                            card_id = target_id
                        end
                    end
                end
                if card_id == target_id then
                    table.insert(target_cards, card)
                    break
                end
            end
        end
    end
    return target_cards
end

function AgentEngine:find_shop_item(target_id)
    local areas = {
        {prefix = "SJ_", zone = G.shop_jokers},
        {prefix = "SV_", zone = G.shop_vouchers},
        {prefix = "SB_", zone = G.shop_booster}
    }
    for _, area in ipairs(areas) do
        if area.zone and area.zone.cards then
            for i, item in ipairs(area.zone.cards) do
                local item_id = item.unique_val or (area.prefix .. tostring(i))
                if item_id == target_id then
                    return item
                end
            end
        end
    end
    return nil
end

function AgentEngine:execute_action(action_json)
    local success, action = pcall(function() return json.decode(action_json) end)
    if not success or type(action) ~= "table" then
        action = { action = "ERROR", message = "Invalid JSON action" }
    end
    
    self:log("Executing Action: " .. tostring(action.action))
    
    if action.action == "ERROR" or action.action == "NO_OP" then
        return
    end

    if action.action == "SELECT_BLIND" then
        if G.FUNCS.select_blind and G.P_BLINDS and G.GAME and G.GAME.blind_on_deck then
            local blind_key = string.lower(G.GAME.blind_on_deck)
            local blind_ref = G.P_BLINDS[blind_key]
            if blind_ref then
                G.FUNCS.select_blind({card = blind_ref})
            end
        end
        return
    elseif action.action == "SKIP" then
        if G.FUNCS.skip_blind then
            G.FUNCS.skip_blind({config = {id = "tag_skip"}})
        end
        return
    elseif action.action == "CASH_OUT" then
        if G.FUNCS.cash_out then
            G.FUNCS.cash_out({config = {id = "cash_out_button"}})
        end
        return
    elseif action.action == "REROLL_SHOP" then
        if G.FUNCS.reroll_shop then
            G.FUNCS.reroll_shop()
        end
        return
    elseif action.action == "NEXT_ROUND" then
        if G.FUNCS.toggle_shop then
            G.FUNCS.toggle_shop()
        end
        return
    elseif action.action == "BUY_CARD" then
        local target = self:find_shop_item(action.target_id)
        if target and G.FUNCS.buy_from_shop then
            G.FUNCS.buy_from_shop({config = {ref_table = target}})
        else
            self:log("Failed to buy shop item: " .. tostring(action.target_id))
        end
        return
    end

    if not G.hand or type(G.hand.cards) ~= "table" then return end

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
        if G.hand.highlighted and #G.hand.highlighted > 0 then
            G.FUNCS.play_cards_from_highlighted()
        else
            self:log("Failed to play: No valid cards highlighted.")
        end
    elseif action.action == "DISCARD" then
        if G.hand.highlighted and #G.hand.highlighted > 0 then
            G.FUNCS.discard_cards_from_highlighted()
        else
            self:log("Failed to discard: No valid cards highlighted.")
        end
    elseif action.action == "SKIP" then
        if G.FUNCS.skip_blind then
            G.FUNCS.skip_blind()
        end
    end
end

function AgentEngine:tick()
    if not G or not G.STATE or not G.STATES then return end
    local phase = self:current_phase()
    if phase ~= "SELECTING_HAND" and phase ~= "BLIND_SELECT" and phase ~= "ROUND_EVAL" and phase ~= "SHOP" then return end
    if G.GAME and G.GAME.blind and G.GAME.blind.boss and G.GAME.blind.boss.name == "The Needle" and G.GAME.current_round.hands_left == 0 then return end
    
    self.is_busy = true
    local state_json = self:serialize_state()
    
    local tcp = socket.tcp()
    tcp:settimeout(self.timeout_sec)
    
    local connected, err = tcp:connect(self.host, self.port)
    if connected then
        tcp:send(state_json .. "\n")
        local response, status, partial = tcp:receive("*l")
        if response then
            self:execute_action(response)
        else
            self:log("No response received from server.")
        end
        tcp:close()
    else
        self:log("Connection failed: " .. tostring(err) .. ". Falling back to manual play.")
    end
    
    -- Free busy lock safely
    if G.E_MANAGER and G.E_MANAGER.add_event then
        G.E_MANAGER:add_event(Event({
            trigger = 'after', delay = 0.4,
            func = function() AgentEngine.is_busy = false; return true end
        }))
    else
        AgentEngine.is_busy = false
    end
end

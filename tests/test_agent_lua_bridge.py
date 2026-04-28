from pathlib import Path


def _agent_source() -> str:
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / "lua" / "agent.lua").read_text(encoding="utf-8")


def test_safe_get_guards_non_table_values():
    source = _agent_source()

    assert 'function AgentEngine:safe_get(t, k)' in source
    assert 'if type(t) ~= "table" then' in source
    assert "return t[k]" in source


def test_blind_selection_resolves_slot_from_ui_state():
    source = _agent_source()

    assert "function AgentEngine:resolve_blind_choice_slot()" in source
    assert "function AgentEngine:get_blind_choice_uibox(blind_slot)" in source
    assert "function AgentEngine:get_blind_choice_button(blind_slot)" in source
    assert "function AgentEngine:prime_blind_choice_button(blind_slot)" in source
    assert 'self:safe_get(blind_states, slot) == "Select"' in source
    assert 'return blind_select_opts[string.lower(blind_slot)]' in source
    assert 'G.GAME.blind_on_deck = blind_slot' in source
    assert 'return blind_ui:get_UIE_by_ID("select_blind_button")' in source
    assert 'G.FUNCS.blind_choice_handler(choice_node)' in source
    assert 'blind_button:click()' in source


def test_agent_bridge_does_not_autostart_from_menu():
    source = _agent_source()

    assert "function AgentEngine:refresh_autostart_state()" not in source
    assert "function AgentEngine:maybe_autostart_run()" not in source
    assert "Auto-start: resumed saved run." not in source
    assert 'G:start_run({ savetext = saved_run })' not in source
    assert 'G:start_run({ stake = stake })' not in source


def test_agent_bridge_uses_transition_gating_not_delay_unlocks():
    source = _agent_source()

    assert "pending_transition_max_polls" in source
    assert "noop_waiting = false" in source
    assert "noop_poll_stride = 10" in source
    assert "game_update_wrapped = false" in source
    assert "function AgentEngine:is_state_settled()" in source
    assert "function AgentEngine:await_pending_transition()" in source
    assert "function AgentEngine:install_update_hook()" in source
    assert "AgentEngine:install_update_hook()" in source
    assert "G.STATE_COMPLETE == true" in source
    assert 'if self.last_request_fingerprint == fingerprint then' in source
    assert 'if self.noop_waiting then' in source
    assert 'if self.noop_poll_counter < self.noop_poll_stride then' in source
    assert "function AgentEngine:unlock_later(" not in source
    assert "function AgentEngine:phase_retry_interval_sec(" not in source
    assert "last_request_at" not in source
    assert "last_menu_action_at" not in source
    assert "autostart_in_progress" not in source
    assert 'if G.shop == nil then' in source
    assert 'if G.round_eval == nil then' in source
    assert 'if G.blind_select == nil then' in source


def test_blind_serialization_uses_resolved_visible_blind():
    source = _agent_source()

    assert "function AgentEngine:get_visible_blind_target_score(phase, visible_blind)" in source
    assert "function AgentEngine:get_visible_blind_ref(phase)" in source
    assert 'local blind_slot = self:resolve_blind_choice_slot()' in source
    assert 'local visible_blind = self:get_visible_blind_ref(phase)' in source
    assert 'local visible_blind_target = self:get_visible_blind_target_score(phase, visible_blind)' in source
    assert 'blind_on_deck = blind_slot' in source
    assert 'target_score = visible_blind_target' in source
    assert 'blind_ui_ready = self:get_blind_choice_uibox(blind_slot) ~= nil' in source


def test_shop_and_round_actions_click_real_ui_buttons():
    source = _agent_source()

    assert "function AgentEngine:find_button_in_tree(root, button_names)" in source
    assert "function AgentEngine:get_shop_next_round_button()" in source
    assert "function AgentEngine:get_shop_reroll_button()" in source
    assert "function AgentEngine:get_shop_item_button(card)" in source
    assert 'cash_out_button:click()' in source
    assert 'reroll_button:click()' in source
    assert 'next_round_button:click()' in source
    assert 'buy_button:click()' in source
    assert 'G.FUNCS.cash_out(cash_out_button)' not in source
    assert 'G.FUNCS.reroll_shop()' not in source
    assert 'G.FUNCS.toggle_shop()' not in source
    assert 'G.FUNCS.buy_from_shop({ config = { ref_table = target } })' not in source


def test_no_op_actions_are_not_spam_logged():
    source = _agent_source()

    assert 'if action.action == "NO_OP" then' in source
    assert 'return "NO_OP", tostring(action.message or "")' in source
    no_op_index = source.index('if action.action == "NO_OP" then')
    log_index = source.index('self:log("Executing Action: " .. tostring(action.action))')
    assert no_op_index < log_index


def test_shop_readiness_waits_for_score_animation_to_finish():
    source = _agent_source()

    assert "function AgentEngine:is_shop_ready()" in source
    assert '(self:safe_get(game, "chips") or 0) == 0' in source
    assert "and self:shop_item_count() > 0" in source


def test_agent_bridge_serializes_deck_key_and_interest_flags():
    source = _agent_source()

    assert "function AgentEngine:normalize_string_field(value, depth)" in source
    assert 'deck_key = self:normalize_string_field(self:safe_get(game, "selected_back_key")) or self:normalize_string_field(self:safe_get(game, "selected_back"))' in source
    assert 'no_interest = self:safe_get(self:safe_get(game, "modifiers"), "no_interest") or self:safe_get(self:safe_get(game, "starting_params"), "no_interest") or false' in source


def test_agent_bridge_serializes_pack_phase_and_items():
    source = _agent_source()

    assert 'if G.STATES.TAROT_PACK and G.STATE == G.STATES.TAROT_PACK then return "PACK_CHOICE" end' in source
    assert 'function AgentEngine:current_pack_kind()' in source
    assert 'function AgentEngine:get_pack_cards()' in source
    assert 'pack_kind = self:current_pack_kind() or ""' in source
    assert 'consumables = {}' in source
    assert 'pack_items = {}' in source
    assert 'table.insert(state.consumables, self:serialize_shop_item(consumable, "CNS_" .. tostring(i)))' in source
    assert 'table.insert(state.pack_items, self:serialize_shop_item(item, "PK_" .. tostring(i)))' in source
    assert 'if action.action == "TAKE_PACK_CARD" then' in source

# Runtime Flow

The runtime loop is intentionally conservative. The Lua bridge only sends requests when the current phase is settled and the relevant UI is ready. The Python server can return `NO_OP` while deeper hand planning continues in the background.

## End-to-End Sequence

```mermaid
sequenceDiagram
    participant Game as Balatro
    participant Lua as Lua AgentEngine
    participant TCP as Local TCP Socket
    participant Server as Python AgentServer
    participant Planner as Planner

    Game->>Lua: Game.update hook
    Lua->>Lua: Check state settled and phase ready
    Lua->>Lua: Serialize BalatroState JSON
    Lua->>TCP: Send JSON line
    TCP->>Server: handle_request(data)
    Server->>Planner: plan_action(state)
    Planner-->>Server: ActionResponse
    Server-->>TCP: JSON action line
    TCP-->>Lua: response
    Lua->>Game: Click/play/discard/cash out
    Lua->>Lua: Record pending transition
```

## Phase Readiness

```mermaid
stateDiagram-v2
    [*] --> UNKNOWN
    UNKNOWN --> BLIND_SELECT: blind UI ready
    UNKNOWN --> SELECTING_HAND: hand cards present
    UNKNOWN --> ROUND_EVAL: cash-out button ready
    UNKNOWN --> SHOP: shop loaded and score animation done
    UNKNOWN --> PACK_CHOICE: pack cards present

    BLIND_SELECT --> Request
    SELECTING_HAND --> Request
    ROUND_EVAL --> Request
    SHOP --> Request
    PACK_CHOICE --> Request

    Request --> ExecuteAction: non-NO_OP response
    Request --> Wait: NO_OP planning_started/planning_pending
    Wait --> Request: poll stride elapsed
    ExecuteAction --> PendingTransition
    PendingTransition --> UNKNOWN: flow token changes
```

## Async Selecting-Hand Flow

```mermaid
sequenceDiagram
    participant Lua
    participant Server
    participant Worker as Background Planner

    Lua->>Server: SELECTING_HAND state
    Server->>Worker: start planning
    Server-->>Lua: NO_OP planning_started
    Lua->>Lua: wait with poll stride
    Lua->>Server: same state
    Server-->>Lua: NO_OP planning_pending
    Worker-->>Server: action ready
    Lua->>Server: same state
    Server-->>Lua: cached final action
```

## Action Execution Surface

```mermaid
flowchart TD
    A["ActionResponse"] --> B{action}
    B -->|"SELECT_BLIND"| C["Resolve blind slot and click select button"]
    B -->|"SKIP"| D["Click skip blind button"]
    B -->|"PLAY_HAND"| E["Highlight hand cards and play"]
    B -->|"DISCARD"| F["Highlight hand cards and discard"]
    B -->|"CASH_OUT"| G["Click cash out"]
    B -->|"REROLL_SHOP"| H["Click shop reroll"]
    B -->|"BUY_CARD"| I["Find shop item and click buy/use"]
    B -->|"NEXT_ROUND"| J["Click next round"]
    B -->|"TAKE_PACK_CARD"| K["Find pack card and click use"]
    B -->|"NO_OP"| L["Do nothing and maybe poll later"]
```

## Protocol Shape

```mermaid
classDiagram
    class BalatroState {
      MetaState meta
      BlindState blind
      EconomyState economy
      Card[] hand
      Joker[] jokers
      Card[] deck
      Card[] discard_pile
      ShopItemState[] shop_items
      ShopItemState[] pack_items
    }

    class ActionResponse {
      string action
      string[] cards
      string target_id
      string message
    }

    BalatroState --> ActionResponse : planner returns
```

The transport is deliberately simple: one JSON request line in, one JSON action line out. This keeps LuaSocket integration predictable and easy to inspect in logs.


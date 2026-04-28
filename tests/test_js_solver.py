from pathlib import Path


def _solver_source() -> str:
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / "scripts" / "balatro_round_solver.js").read_text(encoding="utf-8")


def test_js_solver_uses_boss_modifier_for_boss_flags():
    source = _solver_source()

    assert "function bossName(state)" in source
    assert "state.blind?.boss_modifier" in source
    assert 'TheFlint: bossName(state) === "The Flint"' in source
    assert 'TheEye: bossName(state) === "The Eye"' in source

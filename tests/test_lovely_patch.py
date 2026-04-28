from pathlib import Path
import tomllib


def test_lovely_patch_file_is_valid_and_loads_agent_bridge():
    repo_root = Path(__file__).resolve().parent.parent
    lovely_path = repo_root / "lua" / "lovely.toml"

    with lovely_path.open("rb") as handle:
        data = tomllib.load(handle)

    assert data["manifest"]["version"] == "1.0.0"
    assert data["manifest"]["priority"] == 0

    patches = data["patches"]
    assert isinstance(patches, list)
    assert len(patches) == 1

    copy_patch = next(patch["copy"] for patch in patches if "copy" in patch)
    assert copy_patch["target"] == "game.lua"
    assert copy_patch["position"] == "append"
    assert copy_patch["sources"] == ["agent.lua"]

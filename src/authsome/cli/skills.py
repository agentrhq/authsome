"""Skill management for the Authsome CLI."""

import importlib.resources
import shutil
from pathlib import Path

from loguru import logger

AGENT_SKILL_PATHS = {
    "claude": Path.home() / ".claude" / "skills" / "authsome",
    "hermes": Path.home() / ".agents" / "skills" / "authsome",
    "global": Path.home() / ".skills" / "authsome",
}

# Alias mapping for agents mentioned in issue #146
AGENT_ALIASES = {
    "claude": "claude",
    "claude-code": "claude",
    "hermes": "hermes",
    "hermes-agent": "hermes",
    "codex": "global",
    "open-code": "global",
    "opencode": "global",
    "open-claw": "global",
    "openclaw": "global",
    "nano-claw": "global",
    "nanoclaw": "global",
    "cowork": "global",
}


def install_skill(agent: str | None = None) -> list[Path]:
    """Install the authsome skill for the specified agent or globally."""
    installed_paths = []

    # Determine target paths
    targets = []
    if agent:
        agent_key = AGENT_ALIASES.get(agent.lower(), "global")
        targets.append(AGENT_SKILL_PATHS.get(agent_key, AGENT_SKILL_PATHS["global"]))
    else:
        # If no agent specified, install to all known paths
        targets = list(AGENT_SKILL_PATHS.values())

    # Get skill files from bundled resources
    try:
        skill_files = importlib.resources.files("authsome.skills.authsome")
    except ModuleNotFoundError:
        logger.error("Authsome skill files not found in package.")
        return []

    for target_dir in targets:
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        skill_md = skill_files / "SKILL.md"
        if skill_md.is_file():
            shutil.copy(str(skill_md), str(target_dir / "SKILL.md"))

        # Copy evals if present
        evals_dir = skill_files / "evals"
        if evals_dir.is_dir():
            target_evals = target_dir / "evals"
            target_evals.mkdir(exist_ok=True)
            for eval_file in evals_dir.iterdir():
                if eval_file.is_file():
                    shutil.copy(str(eval_file), str(target_evals / eval_file.name))

        installed_paths.append(target_dir)
        logger.info(f"Installed authsome skill to {target_dir}")

    return installed_paths


def ensure_skill_installed(command: list[str]) -> None:
    """Check if the command is a supported agent and ensure the skill is installed."""
    if not command:
        return

    agent_name = command[0].lower()
    # Handle cases like 'uvx claude' or 'npx claude'
    if agent_name in ("uvx", "npx", "pipx") and len(command) > 1:
        agent_name = command[1].lower()

    if agent_name in AGENT_ALIASES:
        try:
            install_skill(agent_name)
        except Exception as e:
            logger.warning(f"Failed to auto-install skill for {agent_name}: {e}")

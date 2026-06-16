"""CLI command registration."""

import authsome.cli.commands.agent as agent_module
import authsome.cli.commands.connections as connections_module
import authsome.cli.commands.core as core_module
import authsome.cli.commands.daemon as daemon_module
import authsome.cli.commands.provider as provider_module


def register_commands(cli) -> None:
    """Attach command groups and root commands to the root CLI."""
    cli.add_command(core_module.login)
    cli.add_command(core_module.onboard)
    cli.add_command(core_module.logout)
    cli.add_command(core_module.run)
    cli.add_command(core_module.whoami)
    cli.add_command(core_module.doctor)
    cli.add_command(core_module.log_cmd)
    cli.add_command(provider_module.provider)
    cli.add_command(connections_module.connections)
    cli.add_command(agent_module.agent)
    cli.add_command(daemon_module.daemon)

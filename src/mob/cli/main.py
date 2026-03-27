"""Main CLI entry point for mob."""

import click

from mob.cli.commands.org import org, orgs
from mob.cli.commands.domain import domain, domains
from mob.cli.commands.user import user, users
from mob.cli.commands.group import group, groups
from mob.cli.commands.agent import agent, agents
from mob.cli.commands.session import session, sessions
from mob.cli.commands.skill import skill, skills
from mob.cli.commands.config_cmd import config, configs
from mob.cli.commands.env_cmd import env, envs
from mob.cli.commands.init_cmd import init
from mob.cli.commands.migrate_cmd import migrate
from mob.cli.commands.server import serve


@click.group()
@click.version_option(package_name="mob")
def cli():
    """mob - AI Agent Orchestration Platform."""
    pass


cli.add_command(orgs)
cli.add_command(org)
cli.add_command(domains)
cli.add_command(domain)
cli.add_command(users)
cli.add_command(user)
cli.add_command(groups)
cli.add_command(group)
cli.add_command(agents)
cli.add_command(agent)
cli.add_command(sessions)
cli.add_command(session)
cli.add_command(skills)
cli.add_command(skill)
cli.add_command(configs)
cli.add_command(config)
cli.add_command(envs)
cli.add_command(env)
cli.add_command(init)
cli.add_command(migrate)
cli.add_command(serve)


if __name__ == "__main__":
    cli()

"""TUI commands for mob — agent session explorer."""

import os
import shutil

import click
import libtmux
from libtmux.constants import PaneDirection

SESSION_NAME = "mob-tui"
ENV_RIGHT_PANE = "MOB_TUI_RIGHT_PANE_ID"
ENV_SELECTED_SESSION = "MOB_TUI_SESSION_ID"


@click.command("tui")
@click.argument("ref", required=False)
def tui(ref):
    """Launch the agent session explorer TUI.

    Opens a split-pane tmux session: agent list on the left (20%),
    log output on the right (80%). Navigate with j/k, press q to quit.

    Optionally pass a session REF (name, position, or UUID) to pre-select it.

    Requires tmux. For full color support add to ~/.tmux.conf:
      set -g default-terminal "tmux-256color"
      set -ga terminal-overrides ",*256col*:Tc"
    """
    if not shutil.which("tmux"):
        raise click.ClickException("tmux is not installed or not in PATH.")

    # Resolve session reference before creating tmux session so errors surface cleanly.
    session_id = None
    if ref:
        from mob.cli.resolver import resolve_ref
        session_id = resolve_ref("session", ref)

    server = libtmux.Server()
    existing = server.sessions.get(session_name=SESSION_NAME, default=None)
    if existing is not None:
        _switch_to_session(SESSION_NAME)

    session = server.new_session(session_name=SESSION_NAME, window_name="mob-tui")
    window = session.active_window
    left_pane = window.active_pane

    # Split: new right pane takes 80% of window width; left pane keeps 20%.
    right_pane = left_pane.split(direction=PaneDirection.Right, size="80%")

    right_pane.send_keys("echo 'Select an agent to view its logs'", enter=True)

    env_vars = f"{ENV_RIGHT_PANE}={right_pane.pane_id}"
    if session_id:
        env_vars += f" {ENV_SELECTED_SESSION}={session_id}"
    left_pane.send_keys(f"{env_vars} mob tui-app", enter=True)

    left_pane.select()
    _switch_to_session(SESSION_NAME)


def _switch_to_session(session_name: str) -> None:
    """Switch to a tmux session without nesting.

    Uses switch-client when already inside tmux, attach-session otherwise.
    Replaces the current process via execvp so the caller shell regains
    control when the session is eventually detached or destroyed.
    """
    if os.environ.get("TMUX"):
        os.execvp("tmux", ["tmux", "switch-client", "-t", session_name])
    else:
        os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])


@click.command("tui-app", hidden=True)
def tui_app():
    """Internal: run the Textual agent explorer (do not call directly)."""
    from mob.cli.commands.tui_app import AgentExplorerApp

    right_pane_id = os.environ.get(ENV_RIGHT_PANE)
    selected_session_id = os.environ.get(ENV_SELECTED_SESSION)
    app = AgentExplorerApp(right_pane_id=right_pane_id, selected_session_id=selected_session_id)
    app.run()

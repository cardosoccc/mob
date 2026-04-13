"""Textual AgentExplorerApp — runs inside the left tmux pane."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Label, ListItem, ListView

STATE_COLORS: dict[str, str] = {
    "idle": "green",
    "busy": "yellow",
    "pending": "blue",
    "starting": "blue",
    "finished": "dim",
    "failed": "red",
}


class VimListView(ListView):
    """ListView with vi-style j/k navigation bindings."""

    BINDINGS = [
        *ListView.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


class AgentExplorerApp(App):
    """Agent session explorer TUI — left pane of the mob-tui tmux session."""

    CSS = """
    VimListView {
        width: 100%;
        height: 1fr;
        border: none;
    }
    Footer {
        height: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, right_pane_id: str | None, selected_session_id: str | None) -> None:
        super().__init__()
        self._right_pane_id = right_pane_id
        self._selected_session_id = selected_session_id
        self._current_log_session_id: str | None = None

    def compose(self) -> ComposeResult:
        yield VimListView(id="session-list")
        yield Footer()

    def on_mount(self) -> None:
        # Trigger an immediate fetch on mount, then poll every 3 seconds.
        self._enqueue_refresh()
        self.set_interval(3.0, self._enqueue_refresh)
        self.set_interval(5.0, self._refresh_logs)

    # ------------------------------------------------------------------
    # Session list polling
    # ------------------------------------------------------------------

    def _enqueue_refresh(self) -> None:
        self.run_worker(self._fetch_and_update, thread=True, exclusive=True, group="refresh")

    def _fetch_and_update(self) -> None:
        from mob.cli.client import api_get

        try:
            sessions = api_get("/sessions") or []
        except Exception:
            sessions = []
        self.call_from_thread(self._apply_sessions, sessions)

    def _apply_sessions(self, sessions: list) -> None:
        lv = self.query_one("#session-list", VimListView)

        # Remember the currently highlighted session so we can restore focus.
        highlighted_id: str | None = None
        if lv.highlighted_child is not None:
            highlighted_id = lv.highlighted_child.id

        lv.clear()
        for s in sessions:
            color = STATE_COLORS.get(s["state"], "white")
            label = Label(
                f"[{color}]{s['name']}[/{color}]  [{color}]{s['state']}[/{color}]",
                markup=True,
            )
            lv.append(ListItem(label, id=s["id"]))

        # Restore previously highlighted item if it's still in the list.
        restore_id = self._selected_session_id or highlighted_id
        if restore_id:
            for i, item in enumerate(lv.query(ListItem)):
                if item.id == restore_id:
                    lv.index = i
                    if restore_id == self._selected_session_id:
                        # Pre-select fires log display once on first load.
                        self._show_logs(restore_id)
                        self._selected_session_id = None
                    break

    # ------------------------------------------------------------------
    # Log display in right tmux pane
    # ------------------------------------------------------------------

    def _refresh_logs(self) -> None:
        """Periodically re-issue the log command for the current session."""
        if self._current_log_session_id:
            self._show_logs(self._current_log_session_id)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        session_id = event.item.id
        if session_id == self._current_log_session_id:
            return  # already displayed — no-op
        self._show_logs(session_id)

    def _show_logs(self, session_id: str) -> None:
        self._current_log_session_id = session_id
        self.run_worker(
            lambda: self._update_right_pane(session_id),
            thread=True,
            group="logs",
            exclusive=True,
        )

    def _update_right_pane(self, session_id: str) -> None:
        if not self._right_pane_id:
            return
        import libtmux

        try:
            server = libtmux.Server()
            pane = server.panes.get(pane_id=self._right_pane_id, default=None)
            if pane is None:
                return
            pane.send_keys("C-c", literal=True)
            pane.send_keys(f"mob session logs {session_id} --tail 200", enter=True)
        except Exception:
            pass  # right-pane failures are non-fatal

    # ------------------------------------------------------------------
    # Quit: kill the mob-tui tmux session before exiting.
    # ------------------------------------------------------------------

    def action_quit(self) -> None:
        import libtmux

        try:
            server = libtmux.Server()
            session = server.sessions.get(session_name="mob-tui", default=None)
            if session:
                session.kill()
        except Exception:
            pass
        self.exit()

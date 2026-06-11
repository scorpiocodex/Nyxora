"""
Nyxora TUI v3.0.0 "Nexus" — NyxoraApp shell.

Layout:
    ┌─────────────────────────────────────────────────┐
    │  ◆ NYXORA  Tactical Secrets Vault  v{ver}  [■]  │  ← header (1 row)
    ├───────────┬─────────────────────────────────────┤
    │ NAVIGATE  │                                     │
    │ > 1 Vault │         Workspace content           │
    │   2 Manage│         (ContentSwitcher)           │
    │   3 Backup│                                     │
    │   4 Recov.│                                     │
    │   5 Update│                                     │
    │   6 Genera│                                     │
    │   7 Securi│                                     │
    │───────────│                                     │
    │ v{ver}    │                                     │
    └───────────┴─────────────────────────────────────┘
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    ContentSwitcher,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from nyxora import __version__
from nyxora.tui.screens.vault    import VaultScreen
from nyxora.tui.screens.manage   import ManageScreen
from nyxora.tui.screens.backup   import BackupScreen
from nyxora.tui.screens.recovery import RecoveryScreen
from nyxora.tui.screens.updates  import UpdatesScreen
from nyxora.tui.screens.generate import GenerateScreen
from nyxora.tui.screens.security import SecurityScreen


# ── Sidebar nav item ─────────────────────────────────────────────

class NavItem(ListItem):
    """A single sidebar navigation entry."""

    def __init__(self, key: str, label: str, screen_id: str) -> None:
        self._key = key
        self._label = label
        self._screen_id = screen_id
        super().__init__(
            Label(f" {key}  {label}", classes="nav-label"),
            id=f"nav-{screen_id}",
        )
        self.screen_id = screen_id


# ── Main application ─────────────────────────────────────────────

class NyxoraApp(App):
    """
    Nyxora v3.0.0 "Nexus" TUI application.

    Parameters
    ----------
    start_screen : str
        Which screen to activate on mount.
        One of: 'create', 'unlock', 'vault', 'manage', 'backup',
                'recovery', 'updates', 'generate', 'security'
    exe_mode : bool
        True when launched from nyx.exe (not via `nyx tui`).
        Controls whether Escape / q tries to quit or just locks.
    """

    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("1", "navigate('vault')",    "Vault",    show=False),
        Binding("2", "navigate('manage')",   "Manage",   show=False),
        Binding("3", "navigate('backup')",   "Backup",   show=False),
        Binding("4", "navigate('recovery')", "Recovery", show=False),
        Binding("5", "navigate('updates')",  "Updates",  show=False),
        Binding("6", "navigate('generate')", "Generate", show=False),
        Binding("7", "navigate('security')", "Security", show=False),
        Binding("q", "quit",                 "Quit",     show=True),
        Binding("?", "show_help",            "Help",     show=True),
    ]

    # sidebar nav items — order matches key bindings 1-7
    NAV_ITEMS = [
        ("1", "◆  Vault",    "vault"),
        ("2", "≡  Manage",   "manage"),
        ("3", "⊞  Backup",   "backup"),
        ("4", "⟳  Recovery", "recovery"),
        ("5", "↑  Updates",  "updates"),
        ("6", "⚡ Generate", "generate"),
        ("7", "⊛  Security", "security"),
    ]

    def __init__(
        self,
        start_screen: str = "manage",
        exe_mode: bool = False,
    ) -> None:
        super().__init__()
        self.start_screen = start_screen
        self.exe_mode = exe_mode
        self._active_screen = "manage"

    # ── Layout ──────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield self._build_header()
        with Horizontal(id="app-body"):
            yield self._build_sidebar()
            with ContentSwitcher(
                id="workspace",
                initial="screen-manage",
            ):
                yield VaultScreen(   id="screen-vault")
                yield ManageScreen(  id="screen-manage")
                yield BackupScreen(  id="screen-backup")
                yield RecoveryScreen(id="screen-recovery")
                yield UpdatesScreen( id="screen-updates")
                yield GenerateScreen(id="screen-generate")
                yield SecurityScreen(id="screen-security")
        yield Footer()

    def _build_header(self) -> Static:
        locked_state = self._get_vault_status()
        status_class = "status-unlocked" if locked_state == "UNLOCKED" else "status-locked"
        return Static(
            f" ◆ NYXORA  Tactical Secrets Vault  v{__version__}"
            f"  [{locked_state}]",
            id="app-header",
            classes=status_class,
        )

    def _build_sidebar(self) -> Vertical:
        items = []
        for key, label, screen_id in self.NAV_ITEMS:
            items.append(NavItem(key, label, screen_id))

        lv = ListView(*items, id="nav-list")

        sidebar = Vertical(
            Static(" NAVIGATE", id="sidebar-title"),
            lv,
            Static(
                f" nyxora v{__version__}\n scorpiocodex",
                id="sidebar-footer",
            ),
            id="sidebar",
        )
        return sidebar

    # ── Mount ────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Route to the correct starting screen."""
        if self.start_screen == "create":
            from nyxora.tui.screens.unlock import CreateVaultScreen
            self.push_screen(CreateVaultScreen(), self._on_vault_ready)
        elif self.start_screen == "unlock":
            from nyxora.tui.screens.unlock import UnlockScreen
            self.push_screen(UnlockScreen(), self._on_vault_ready)
        else:
            target = self.start_screen if self.start_screen in (
                "vault", "manage", "backup", "recovery",
                "updates", "generate", "security"
            ) else "manage"
            self._switch_to(target)

    def _on_vault_ready(self, success: bool) -> None:
        """Called when UnlockScreen or CreateVaultScreen dismisses."""
        if success:
            self._switch_to("manage")
            # Manage is already the current switcher child beneath the
            # unlock overlay, so the switch fires no Show event — reload
            # explicitly now that a session exists.
            self.query_one(ManageScreen).reload_entries()
            self._update_header_status()
            self.notify(
                "Vault unlocked. Welcome to Nyxora.",
                title="◆ UNLOCKED",
                timeout=3,
            )
        else:
            self.exit()

    # ── Navigation ───────────────────────────────────────────────

    def action_navigate(self, screen_id: str) -> None:
        """Switch the workspace to the named screen."""
        self._switch_to(screen_id)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Gate App-level bindings by focus and overlay state.

        - While an abandonable-work overlay is active (AddEntry / EditEntry
          form, or the TOTP QR overlay), suppress both quit and navigate so
          the user can't accidentally quit the app or jump sections and lose
          a half-filled form or a mid-scan QR. They leave via the overlay's
          own Esc binding first.
        - Unlock / CreateVault screens are intentionally NOT in this set: at
          the lock screen (cold launch or mid-session relock) q should quit
          and digits should reach the master password Input.
        - While an Input has focus, suppress navigate so digits 1-7 reach
          the field (master password, search box).
        """
        if action in ("quit", "navigate"):
            from nyxora.tui.screens.add_entry import AddEntryScreen
            from nyxora.tui.screens.edit_entry import EditEntryScreen
            from nyxora.tui.screens.totp_qr_overlay import TotpQrOverlay
            if isinstance(
                self.screen,
                (AddEntryScreen, EditEntryScreen, TotpQrOverlay),
            ):
                return False
        if action.startswith("navigate") and isinstance(self.focused, Input):
            return False
        return True

    def _switch_to(self, screen_id: str) -> None:
        """Update ContentSwitcher and highlight the matching nav item."""
        switcher = self.query_one("#workspace", ContentSwitcher)
        switcher.current = f"screen-{screen_id}"
        self._active_screen = screen_id
        self._update_nav_highlight(screen_id)
        self._update_header_status()

    def _update_nav_highlight(self, screen_id: str) -> None:
        """Move the amber highlight to the active nav item."""
        try:
            nav_list = self.query_one("#nav-list", ListView)
            for item in nav_list.query(NavItem):
                if item.screen_id == screen_id:
                    nav_list.index = list(nav_list.query(NavItem)).index(item)
                    break
        except Exception:
            pass

    def _update_header_status(self) -> None:
        """Refresh the vault status badge in the header."""
        try:
            status = self._get_vault_status()
            header = self.query_one("#app-header", Static)
            header.update(
                f" ◆ NYXORA  Tactical Secrets Vault  v{__version__}"
                f"  [{status}]"
            )
            header.remove_class("status-unlocked", "status-locked")
            if status == "UNLOCKED":
                header.add_class("status-unlocked")
            else:
                header.add_class("status-locked")
        except Exception:
            pass

    def _get_vault_status(self) -> str:
        """Return 'UNLOCKED' or 'LOCKED' based on current session."""
        try:
            from nyxora.cli.helpers import load_session
            return "UNLOCKED" if load_session() is not None else "LOCKED"
        except Exception:
            return "LOCKED"

    # ── ListView events ──────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle sidebar click navigation."""
        if isinstance(event.item, NavItem):
            self._switch_to(event.item.screen_id)

    # ── Other actions ────────────────────────────────────────────

    def action_show_help(self) -> None:
        """Show a brief help notification."""
        self.notify(
            "1-7 navigate · q quit · ? help\n"
            "In Manage: a add · e edit · d delete · c copy · t TOTP",
            title="◆ NYXORA Keybindings",
            timeout=6,
        )

    def action_quit(self) -> None:
        if self.exe_mode:
            try:
                from nyxora.cli.helpers import load_session, clear_session
                from nyxora.core.memory_guard import wipe_memory

                session = load_session()
                if session is not None:
                    _, _vp, root_key = session
                    wipe_memory(root_key)

                clear_session()

            except Exception:
                pass
        self.exit()


# ── CLI entry point (used by `nyx tui` command) ──────────────────

def launch_tui(start_screen: str | None = None) -> None:
    """
    Called by src/nyxora/cli/commands/tui_cmd.py.
    Routes to the correct screen based on vault state,
    same as the exe launcher.
    """
    if start_screen is None:
        from nyxora.tui.launcher import _resolve_start_screen
        start_screen = _resolve_start_screen()
    app = NyxoraApp(start_screen=start_screen, exe_mode=False)
    app.run()

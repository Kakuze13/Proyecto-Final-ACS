from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft

from client.command_handler import new_request
from client.tcp_client import TcpClient


BG = "#1e1f22"
SERVER_BAR = "#111214"
SIDEBAR = "#2b2d31"
PANEL = "#313338"
INPUT = "#383a40"
TEXT = "#f2f3f5"
MUTED = "#949ba4"
ACCENT = "#5865f2"
GREEN = "#23a559"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class ChatRoomApp:
    """Flet desktop client with a dark, Discord-inspired chat layout."""

    def __init__(self, page: ft.Page, host: str, port: int) -> None:
        self.page = page
        self.default_host = host
        self.default_port = port
        self.client: TcpClient | None = None
        self.username = ""
        self.selected_room: str | None = None
        self.joined_rooms: set[str] = set()
        self.room_names: list[str] = []
        self.room_owners: dict[str, str] = {}
        self.messages: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = {}
        self.members: list[str] = []
        self._sending = False
        self._closing = False
        self._event_task: asyncio.Task[None] | None = None

        page.title = "ChatRoom"
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed=ACCENT)
        page.bgcolor = BG
        page.padding = 0
        page.spacing = 0
        page.window.width = 1180
        page.window.height = 760
        page.window.icon = str(ASSETS_DIR / "icon.ico")
        page.window.min_width = 540
        page.window.min_height = 360
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event
        page.on_disconnect = self._on_disconnect
        page.on_resize = self._on_resize
        self._build_login()

    def _build_login(self) -> None:
        self.username_field = ft.TextField(
            label="Nombre de usuario",
            hint_text="3-20 letras, números o _",
            autofocus=True,
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            border=ft.OutlineInputBorder(border_radius=10),
            bgcolor=INPUT,
            on_submit=self._connect,
        )
        self.host_field = ft.TextField(
            label="Servidor",
            value=self.default_host,
            prefix_icon=ft.Icons.DNS_OUTLINED,
            border=ft.OutlineInputBorder(border_radius=10),
            bgcolor=INPUT,
        )
        self.port_field = ft.TextField(
            label="Puerto",
            value=str(self.default_port),
            width=150,
            prefix_icon=ft.Icons.ROUTER_OUTLINED,
            border=ft.OutlineInputBorder(border_radius=10),
            bgcolor=INPUT,
            on_submit=self._connect,
        )
        self.login_status = ft.Text("Conéctate al servidor para abrir ChatRoom.", color=MUTED)
        self.connect_button = ft.Button(
            content="Conectar",
            icon=ft.Icons.LOGIN,
            on_click=self._connect,
            bgcolor=ACCENT,
            color=TEXT,
            height=46,
        )
        card = ft.Container(
            width=460,
            padding=36,
            border_radius=16,
            bgcolor=PANEL,
            content=ft.Column(
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Container(
                        width=58,
                        height=58,
                        alignment=ft.Alignment.CENTER,
                        border_radius=18,
                        bgcolor=ACCENT,
                        content=ft.Icon(ft.Icons.FORUM_ROUNDED, size=30, color=TEXT),
                    ),
                    ft.Text("ChatRoom", size=30, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text("Mensajería por salas en tiempo real", color=MUTED),
                    ft.Container(height=2),
                    self.username_field,
                    self.host_field,
                    ft.Row([self.port_field], alignment=ft.MainAxisAlignment.START),
                    self.login_status,
                    self.connect_button,
                ],
            ),
        )
        page_body = ft.Container(
            expand=True,
            padding=24,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[card],
            ),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=["#17181b", "#24264a"],
            ),
        )
        self.page.clean()
        self.page.add(page_body)

    async def _connect(self, _event: Any = None) -> None:
        username = (self.username_field.value or "").strip()
        host = (self.host_field.value or "").strip()
        try:
            port = int((self.port_field.value or "").strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.login_status.value = "El puerto debe ser un número entre 1 y 65535."
            self.page.update()
            return
        if not username or not host:
            self.login_status.value = "Completa el usuario y el servidor."
            self.page.update()
            return

        self.connect_button.disabled = True
        self.login_status.value = "Conectando…"
        self.page.update()
        client = TcpClient()
        try:
            await client.connect(host, port)
            response = await client.request(new_request("CONNECT", username=username))
            if response.get("type") != "SUCCESS":
                self.login_status.value = response.get("message", "No se pudo conectar.")
                await client.close()
                self.connect_button.disabled = False
                self.page.update()
                return
        except (OSError, asyncio.TimeoutError, ConnectionError) as error:
            await client.close()
            self.login_status.value = f"No se pudo conectar: {error}"
            self.connect_button.disabled = False
            self.page.update()
            return

        self.client = client
        self.username = username
        self._build_chat()
        self._event_task = asyncio.create_task(self._listen_events(client))
        await self._refresh_rooms()

    def _build_chat(self) -> None:
        self.status_text = ft.Text("Conectado", size=12, color=GREEN)
        self.room_list = ft.Column(spacing=3, scroll=ft.ScrollMode.AUTO, expand=True)
        self.message_list = ft.ListView(
            expand=True,
            spacing=18,
            padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            auto_scroll=True,
        )
        self.member_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.room_title = ft.Text("Elige una sala", size=19, weight=ft.FontWeight.BOLD)
        self.room_subtitle = ft.Text("", size=12, color=MUTED)
        self.leave_button = ft.IconButton(
            icon=ft.Icons.EXIT_TO_APP,
            tooltip="Salir de esta sala",
            icon_color=MUTED,
            visible=False,
            on_click=self._leave_room,
        )
        self.delete_button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            tooltip="Eliminar sala",
            icon_color="#ed4245",
            visible=False,
            on_click=self._delete_selected_room,
        )
        self.member_count = ft.Text("INTEGRANTES —", size=11, weight=ft.FontWeight.BOLD, color=MUTED)
        self.room_name_field = ft.TextField(
            hint_text="Crear una sala",
            dense=True,
            bgcolor=INPUT,
            border=ft.OutlineInputBorder(border_radius=8),
            expand=True,
            on_submit=self._create_room,
        )
        self.room_name_field.visible = False
        self.create_room_form = ft.Row(
            spacing=6,
            visible=False,
            controls=[
                self.room_name_field,
                ft.IconButton(
                    icon=ft.Icons.CHECK,
                    tooltip="Crear sala",
                    icon_color=GREEN,
                    on_click=self._create_room,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    tooltip="Cancelar",
                    icon_color=MUTED,
                    on_click=self._toggle_create_room,
                ),
            ],
        )
        self.create_room_toggle = ft.IconButton(
            icon=ft.Icons.ADD,
            icon_size=18,
            tooltip="Crear sala",
            icon_color=MUTED,
            on_click=self._toggle_create_room,
        )
        self.message_field = ft.TextField(
            hint_text="Elige una sala y escribe un mensaje…",
            multiline=True,
            min_lines=1,
            max_lines=5,
            shift_enter=True,
            disabled=True,
            filled=True,
            bgcolor=INPUT,
            border={
                ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                    border_radius=10,
                    side=ft.BorderSide.none(),
                ),
                ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                    border_radius=10,
                    side=ft.BorderSide.none(),
                ),
            },
            expand=True,
            on_submit=self._send_message,
        )
        self.send_button = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            tooltip="Enviar mensaje",
            icon_color=TEXT,
            bgcolor=ACCENT,
            on_click=self._send_message,
            disabled=True,
        )

        self.server_rail = ft.Container(
            width=68,
            bgcolor=SERVER_BAR,
            padding=ft.Padding.symmetric(vertical=14),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Container(
                        width=46,
                        height=46,
                        border_radius=16,
                        bgcolor=ACCENT,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.FORUM_ROUNDED, color=TEXT, size=24),
                        tooltip="ChatRoom",
                    ),
                    ft.Container(width=30, height=2, bgcolor="#3f4147", border_radius=2),
                    ft.Container(
                        width=46,
                        height=46,
                        border_radius=16,
                        bgcolor="#35373c",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("#", size=24, weight=ft.FontWeight.BOLD, color=TEXT),
                        tooltip="Salas",
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        tooltip="Cerrar aplicación",
                        icon_color=MUTED,
                        on_click=self._quit_app,
                    ),
                ],
            ),
        )

        self.channel_sidebar = ft.Container(
            width=244,
            bgcolor=SIDEBAR,
            padding=ft.Padding.only(left=12, right=12, top=0, bottom=10),
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Container(
                        height=58,
                        padding=ft.Padding.symmetric(horizontal=6),
                        border=ft.Border.only(bottom=ft.BorderSide(1, "#202226")),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("ChatRoom", size=16, weight=ft.FontWeight.BOLD),
                                ft.Icon(ft.Icons.EXPAND_MORE, color=MUTED),
                            ],
                        ),
                    ),
                    ft.Container(height=16),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("SALAS", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                            self.create_room_toggle,
                        ],
                    ),
                    self.create_room_form,
                    self.room_list,
                    ft.Container(height=10),
                    ft.Container(
                        padding=10,
                        border_radius=8,
                        bgcolor="#232428",
                        content=ft.Row(
                            spacing=9,
                            controls=[
                                ft.CircleAvatar(
                                    content=ft.Text(self.username[:1].upper(), size=14),
                                    bgcolor=ACCENT,
                                    radius=17,
                                ),
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        ft.Text(self.username, size=12, weight=ft.FontWeight.BOLD),
                                        self.status_text,
                                    ],
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.LOGOUT,
                                    tooltip="Cerrar sesión y volver al inicio",
                                    icon_color="#ed4245",
                                    icon_size=18,
                                    on_click=self._logout_session,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        self.chat_body = ft.Column(
            spacing=0,
            expand=True,
            controls=[
                ft.Container(
                    height=58,
                    padding=ft.Padding.symmetric(horizontal=20),
                    border=ft.Border.only(bottom=ft.BorderSide(1, "#26272b")),
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TAG, color=MUTED, size=20),
                            ft.Column(spacing=0, controls=[self.room_title, self.room_subtitle]),
                            ft.Container(expand=True),
                            self.leave_button,
                            self.delete_button,
                            ft.IconButton(
                                icon=ft.Icons.GROUP_OUTLINED,
                                tooltip="Actualizar integrantes",
                                icon_color=MUTED,
                                on_click=self._load_members,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="Actualizar salas",
                                icon_color=MUTED,
                                on_click=self._refresh_rooms,
                            ),
                        ],
                    ),
                ),
                self.message_list,
                ft.Container(
                    padding=ft.Padding.only(left=20, right=20, top=8, bottom=18),
                    content=ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            ft.Container(
                                expand=True,
                                padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                                bgcolor=INPUT,
                                border_radius=10,
                                content=self.message_field,
                            ),
                            self.send_button,
                        ],
                    ),
                ),
            ],
        )

        self.members_sidebar = ft.Container(
            width=205,
            bgcolor=SIDEBAR,
            padding=ft.Padding.only(left=14, right=14, top=20, bottom=12),
            content=ft.Column(
                spacing=14,
                controls=[self.member_count, self.member_list],
            ),
        )

        self.page.clean()
        self.page.add(
            ft.Row(
                spacing=0,
                expand=True,
                controls=[self.server_rail, self.channel_sidebar, self.chat_body, self.members_sidebar],
            )
        )
        self._render_rooms()
        self._render_members()
        self._on_resize()

    def _on_resize(self, _event: Any = None) -> None:
        if not hasattr(self, "members_sidebar"):
            return
        width = self.page.width or 1180
        self.members_sidebar.visible = width >= 940
        self.server_rail.visible = width >= 680
        self.channel_sidebar.width = 244 if width >= 800 else 188
        self.page.update()

    def _room_tile(self, room: str, member_count: int) -> ft.Control:
        joined = room in self.joined_rooms
        selected = room == self.selected_room
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=6,
            bgcolor="#404249" if selected else "transparent",
            on_click=lambda _e, room_name=room: self._select_room(room_name),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.TAG, size=17, color=TEXT if selected else MUTED),
                    ft.Text(room, size=13, color=TEXT if selected else MUTED, expand=True),
                    ft.Text(str(member_count), size=11, color=MUTED),
                    ft.Icon(ft.Icons.CHECK, size=14, color=GREEN) if joined else ft.Container(width=0),
                ],
            ),
        )

    def _render_rooms(self) -> None:
        if not hasattr(self, "room_list"):
            return
        counts = getattr(self, "room_counts", {})
        self.room_list.controls = [self._room_tile(room, counts.get(room, 0)) for room in self.room_names]
        self.room_list.controls.append(
            ft.Text("No hay salas todavía. Crea la primera.", size=12, color=MUTED)
            if not self.room_names
            else ft.Container(height=0)
        )
        self.room_list.update()

    def _render_members(self) -> None:
        if not hasattr(self, "member_list"):
            return
        self.member_count.value = f"INTEGRANTES — {len(self.members)}"
        self.member_list.controls = [
            ft.Row(
                spacing=9,
                controls=[
                    ft.CircleAvatar(
                        content=ft.Text(name[:1].upper(), size=12),
                        bgcolor=ACCENT if name == self.username else "#4e5058",
                        radius=14,
                    ),
                    ft.Text(name, size=12, color=TEXT if name == self.username else MUTED),
                ],
            )
            for name in self.members
        ] or [ft.Text("Únete a una sala para ver sus integrantes.", size=12, color=MUTED)]
        self.member_list.update()
        self.member_count.update()

    def _render_messages(self, room: str) -> None:
        if not hasattr(self, "message_list"):
            return
        messages = sorted(self.messages.get(room, {}).values(), key=lambda item: item["timestamp"])
        self.message_list.controls = [self._message_card(message) for message in messages]
        if not messages:
            self.message_list.controls = [
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.FORUM_OUTLINED, size=46, color="#555861"),
                            ft.Text(f"Este es el comienzo de #{room}", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text("Envía el primer mensaje de la sala.", color=MUTED),
                        ],
                    ),
                )
            ]
        self.message_list.update()

    def _message_card(self, message: dict[str, Any]) -> ft.Control:
        try:
            stamp = datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))
            time_label = stamp.astimezone().strftime("%b %d, %H:%M")
        except (KeyError, ValueError):
            time_label = ""
        username = str(message.get("username", "Usuario"))
        return ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=12,
            controls=[
                ft.CircleAvatar(
                    content=ft.Text(username[:1].upper(), size=14),
                    bgcolor=ACCENT if username == self.username else "#4e5058",
                    radius=18,
                ),
                ft.Column(
                    spacing=3,
                    expand=True,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Text(username, size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(time_label, size=10, color=MUTED),
                            ],
                        ),
                        ft.Text(str(message.get("content", "")), size=14, color="#dbdee1"),
                    ],
                ),
            ],
        )

    async def _request(self, message_type: str, **fields: Any) -> dict[str, Any]:
        if self.client is None:
            raise ConnectionError("No hay conexión activa con el servidor")
        response = await self.client.request(new_request(message_type, **fields))
        if response.get("type") == "ERROR":
            self._notify(response.get("message", "La operación no se pudo completar."))
        return response

    async def _refresh_rooms(self, _event: Any = None) -> None:
        try:
            response = await self._request("LIST_ROOMS")
            if response.get("type") != "SUCCESS":
                return
            rooms = response.get("data", {}).get("rooms", [])
            self.room_names = [item["room"] for item in rooms]
            self.room_counts = {item["room"]: item["members_count"] for item in rooms}
            self.room_owners = {item["room"]: item["created_by"] for item in rooms}
            self._render_rooms()
            if self.selected_room not in self.room_names:
                self.selected_room = None
                self.room_title.value = "Elige una sala"
                self.room_subtitle.value = ""
                self.message_field.disabled = True
                self.send_button.disabled = True
                self.leave_button.visible = False
                self.delete_button.visible = False
                self.members = []
                self._render_members()
                self.message_list.controls = []
                self.message_list.update()
            if self.selected_room:
                await self._refresh_members()
        except (OSError, ConnectionError, asyncio.TimeoutError) as error:
            self._notify(f"No se pudieron actualizar las salas: {error}")

    async def _create_room(self, _event: Any = None) -> None:
        room = (self.room_name_field.value or "").strip().lower()
        if not room:
            self._notify("Escribe el nombre de la sala que quieres crear.")
            return
        try:
            response = await self._request("CREATE_ROOM", room=room)
            if response.get("type") == "SUCCESS":
                self.room_name_field.value = ""
                self.create_room_form.visible = False
                self.room_name_field.visible = False
                self.create_room_toggle.icon = ft.Icons.ADD
                self.joined_rooms.add(room)
                self.selected_room = room
                await self._refresh_rooms()
                await self._load_history(room)
        except (OSError, ConnectionError, asyncio.TimeoutError) as error:
            self._notify(f"No se pudo crear la sala: {error}")

    def _toggle_create_room(self, _event: Any = None) -> None:
        visible = not self.create_room_form.visible
        self.create_room_form.visible = visible
        self.room_name_field.visible = visible
        self.create_room_toggle.icon = ft.Icons.CLOSE if visible else ft.Icons.ADD
        self.page.update()

    async def _select_room(self, room: str) -> None:
        self.selected_room = room
        self.room_title.value = room
        is_joined = room in self.joined_rooms
        self.room_subtitle.value = "Canal de texto · Ya formas parte de esta sala" if is_joined else "Canal de texto · Únete para conversar"
        self.message_field.disabled = not is_joined
        self.send_button.disabled = not is_joined
        self.leave_button.visible = is_joined
        self.delete_button.visible = self.room_owners.get(room) == self.username
        self._render_rooms()
        if is_joined:
            self._render_messages(room)
            await self._load_history(room)
            await self._refresh_members()
        else:
            self.members = []
            self._render_members()
            self.message_list.controls = [
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.LOCK_OUTLINE, size=40, color=MUTED),
                            ft.Text(f"Únete a #{room} para participar", size=17, weight=ft.FontWeight.BOLD),
                            ft.Button("Unirse a la sala", icon=ft.Icons.LOGIN, on_click=self._join_room, bgcolor=ACCENT),
                        ],
                    ),
                )
            ]
            self.message_list.update()
        self.page.update()

    async def _delete_selected_room(self, _event: Any = None) -> None:
        room = self.selected_room
        if room and self.room_owners.get(room) == self.username:
            self._confirm_delete(room)

    async def _join_room(self, _event: Any = None) -> None:
        room = self.selected_room
        if not room:
            self._notify("Selecciona una sala primero.")
            return
        try:
            response = await self._request("JOIN_ROOM", room=room)
            if response.get("type") == "SUCCESS":
                self.joined_rooms.add(room)
                await self._select_room(room)
                await self._refresh_rooms()
        except (OSError, ConnectionError, asyncio.TimeoutError) as error:
            self._notify(f"No se pudo entrar a la sala: {error}")

    async def _leave_room(self, _event: Any = None) -> None:
        room = self.selected_room
        if not room or room not in self.joined_rooms:
            self._notify("Selecciona una sala a la que ya te hayas unido.")
            return
        response = await self._request("LEAVE_ROOM", room=room)
        if response.get("type") == "SUCCESS":
            self.joined_rooms.discard(room)
            await self._select_room(room)
            await self._refresh_rooms()

    async def _delete_room(self, room: str) -> None:
        response = await self._request("DELETE_ROOM", room=room)
        if response.get("type") == "SUCCESS":
            self.joined_rooms.discard(room)
            self.messages.pop(room, None)
            if self.selected_room == room:
                self.selected_room = None
            await self._refresh_rooms()
            self._notify(f"Sala #{room} y su historial eliminados.")

    def _confirm_delete(self, room: str) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar sala"),
            content=ft.Text(f"¿Eliminar #{room}, su historial y retirar a todos sus integrantes?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _e: self.page.pop_dialog()),
                ft.TextButton(
                    "Eliminar",
                    on_click=lambda _e: self._confirm_delete_action(room),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    async def _confirm_delete_action(self, room: str) -> None:
        self.page.pop_dialog()
        await self._delete_room(room)

    async def _load_history(self, room: str) -> None:
        try:
            response = await self._request("HISTORY", room=room)
            if response.get("type") != "HISTORY_RESULT":
                return
            for message in response.get("messages", []):
                self._store_message(message)
            if self.selected_room == room:
                self._render_messages(room)
            if response.get("truncated"):
                self._notify("El historial se limitó por el tamaño máximo del protocolo.")
        except (OSError, ConnectionError, asyncio.TimeoutError) as error:
            self._notify(f"No se pudo cargar el historial: {error}")

    async def _load_members(self, _event: Any = None) -> None:
        await self._refresh_members()

    async def _refresh_members(self) -> None:
        room = self.selected_room
        if not room or room not in self.joined_rooms:
            return
        try:
            response = await self._request("LIST_USERS", room=room)
            if response.get("type") == "SUCCESS":
                self.members = response.get("data", {}).get("users", [])
                self._render_members()
        except (OSError, ConnectionError, asyncio.TimeoutError) as error:
            self._notify(f"No se pudieron consultar integrantes: {error}")

    async def _send_message(self, _event: Any = None) -> None:
        room = self.selected_room
        content = (self.message_field.value or "").strip()
        if not room or room not in self.joined_rooms:
            self._notify("Únete a una sala antes de enviar mensajes.")
            return
        if not content or self._sending:
            return
        self._sending = True
        self.send_button.disabled = True
        self.page.update()
        try:
            response = await self._request("SEND_MESSAGE", room=room, content=content)
            if response.get("type") == "SUCCESS":
                self.message_field.value = ""
        except (OSError, ConnectionError, asyncio.TimeoutError) as error:
            self._notify(f"No se pudo enviar el mensaje: {error}")
        finally:
            self._sending = False
            self.send_button.disabled = room not in self.joined_rooms
            self.page.update()

    async def _listen_events(self, client: TcpClient) -> None:
        try:
            while not self._closing:
                events = [await client.events.get()]
                # Batch bursts so Flet updates the message list a few times,
                # instead of rebuilding and sending the page for every frame.
                await asyncio.sleep(0.005)
                for _ in range(63):
                    try:
                        events.append(client.events.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                message_controls: list[ft.Control] = []
                refresh_rooms = False
                refresh_members = False
                page_changed = False
                for event in events:
                    event_type = event.get("type")
                    if event_type == "CHAT_MESSAGE":
                        room = event.get("room")
                        key = (
                            event.get("timestamp", ""),
                            event.get("username", ""),
                            event.get("content", ""),
                        )
                        is_new = room not in self.messages or key not in self.messages[room]
                        was_empty = not self.messages.get(room)
                        self._store_message(event)
                        if is_new and self.selected_room == room:
                            if was_empty:
                                self.message_list.controls.clear()
                            message_controls.append(self._message_card(event))
                    elif event_type in {"ROOM_CREATED", "ROOM_DELETED"}:
                        if event_type == "ROOM_DELETED":
                            room = event.get("room")
                            self.joined_rooms.discard(room)
                            self.messages.pop(room, None)
                            if self.selected_room == room:
                                self.selected_room = None
                        refresh_rooms = True
                    elif event_type in {"USER_JOINED", "USER_LEFT"}:
                        refresh_rooms = True
                        refresh_members |= event.get("room") == self.selected_room
                    elif event_type in {"USER_CONNECTED", "USER_DISCONNECTED"}:
                        verb = "se conectó" if event_type == "USER_CONNECTED" else "se desconectó"
                        self._notify(f"{event.get('username', 'Un usuario')} {verb}.")
                        page_changed = True

                if refresh_rooms:
                    await self._refresh_rooms()
                if refresh_members and not refresh_rooms:
                    await self._refresh_members()
                if message_controls:
                    self.message_list.controls.extend(message_controls)
                    self.message_list.update()
                if page_changed:
                    self.page.update()
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            if not self._closing:
                self._notify("Se perdió la conexión con el servidor.")

    def _store_message(self, message: dict[str, Any]) -> None:
        room = message.get("room")
        if not room:
            return
        key = (message.get("timestamp", ""), message.get("username", ""), message.get("content", ""))
        self.messages.setdefault(room, {})[key] = message

    def _notify(self, message: str) -> None:
        if self._closing:
            return
        self.page.show_dialog(
            ft.SnackBar(content=ft.Text(message), duration=3500)
        )

    async def _close_session(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._event_task is not None:
            self._event_task.cancel()
            await asyncio.gather(self._event_task, return_exceptions=True)
        if self.client is not None:
            try:
                await self.client.request(new_request("DISCONNECT"))
            except (OSError, ConnectionError, asyncio.TimeoutError):
                pass
            await self.client.close()
            self.client = None
        self.username = ""
        self.selected_room = None
        self.joined_rooms.clear()
        self.room_names.clear()
        self.room_owners.clear()
        self.messages.clear()
        self.members.clear()

    async def _logout_session(self, _event: Any = None) -> None:
        await self._close_session()
        self._closing = False
        self._build_login()

    async def _quit_app(self, _event: Any = None) -> None:
        await self._close_session()
        self._closing = True
        await self.page.window.destroy()

    async def _on_disconnect(self, _event: Any) -> None:
        self._closing = True
        if self._event_task is not None:
            self._event_task.cancel()
            await asyncio.gather(self._event_task, return_exceptions=True)
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def _on_window_event(self, event: ft.WindowEvent) -> None:
        if event.type == ft.WindowEventType.CLOSE:
            await self._quit_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Interfaz Flet de ChatRoom")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    async def app(page: ft.Page) -> None:
        ChatRoomApp(page, args.host, args.port)

    ft.run(app, assets_dir=str(ASSETS_DIR))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import asyncio
import queue
import threading
import tkinter as tk
from collections.abc import Coroutine
from datetime import datetime
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Any
from concurrent.futures import Future

from client.command_handler import new_request
from client.tcp_client import TcpClient


class ChatRoomApp:
    def __init__(self, root: tk.Tk, host: str, port: int) -> None:
        self.root = root
        self.default_host = host
        self.default_port = port
        self.ui_events: queue.Queue[tuple[str, str, Any]] = queue.Queue()
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(
            target=self._run_loop,
            name="chatroom-network",
            daemon=True,
        )
        self.loop_thread.start()
        self.client: TcpClient | None = None
        self.username = ""
        self.selected_room: str | None = None
        self.joined_rooms: set[str] = set()
        self.room_names: list[str] = []
        self.room_owners: dict[str, str] = {}
        self.messages: dict[str, dict[tuple[str, str, str], dict[str, str]]] = {}
        self.text_size = 12
        self._closing = False
        self._sending = False

        self.root.title("ChatRoom")
        self.root.geometry("1050x680")
        self.root.minsize(760, 520)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_login()
        self.root.after(50, self._process_ui_events)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()

    def _submit(
        self,
        coroutine: Coroutine[Any, Any, dict[str, Any]],
        action: str,
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)

        def completed(result: Future[dict[str, Any]]) -> None:
            try:
                value = result.result()
            except Exception as error:
                self.ui_events.put(("error", action, str(error)))
            else:
                self.ui_events.put(("result", action, value))

        future.add_done_callback(completed)

    async def _connect(self, host: str, port: int, username: str) -> dict[str, Any]:
        client = TcpClient()
        try:
            await client.connect(host, port)
            response = await client.request(new_request("CONNECT", username=username))
            if response.get("type") == "SUCCESS":
                self.client = client
                self.username = username
                asyncio.create_task(self._forward_events(client))
                return response
            return response
        finally:
            if self.client is not client:
                await client.close()

    async def _forward_events(self, client: TcpClient) -> None:
        while True:
            event = await client.events.get()
            self.ui_events.put(("event", "", event))

    async def _request(self, message_type: str, **fields: Any) -> dict[str, Any]:
        if self.client is None:
            raise ConnectionError("No hay una conexión activa con el servidor")
        return await self.client.request(new_request(message_type, **fields))

    def _build_login(self) -> None:
        self.login_frame = ttk.Frame(self.root, padding=32)
        self.login_frame.pack(expand=True)
        self.login_frame.columnconfigure(1, weight=1)

        ttk.Label(
            self.login_frame,
            text="ChatRoom",
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(
            self.login_frame,
            text="Mensajería por salas en tiempo real",
            font=("Segoe UI", 12),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 24))

        ttk.Label(self.login_frame, text="Usuario (3-20 letras, números o _):").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=8
        )
        self.username_entry = ttk.Entry(self.login_frame, width=32)
        self.username_entry.grid(row=2, column=1, sticky="ew", pady=8)

        ttk.Label(self.login_frame, text="Servidor:").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=8
        )
        self.host_entry = ttk.Entry(self.login_frame, width=32)
        self.host_entry.insert(0, self.default_host)
        self.host_entry.grid(row=3, column=1, sticky="ew", pady=8)

        ttk.Label(self.login_frame, text="Puerto:").grid(
            row=4, column=0, sticky="w", padx=(0, 12), pady=8
        )
        self.port_entry = ttk.Entry(self.login_frame, width=12)
        self.port_entry.insert(0, str(self.default_port))
        self.port_entry.grid(row=4, column=1, sticky="w", pady=8)

        self.status_var = tk.StringVar(value="Ingresa tus datos para conectarte.")
        ttk.Label(
            self.login_frame,
            textvariable=self.status_var,
            wraplength=420,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 4))

        self.connect_button = ttk.Button(
            self.login_frame,
            text="Conectar",
            command=self._connect_from_form,
        )
        self.connect_button.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.username_entry.bind("<Return>", lambda _event: self._connect_from_form())
        self.port_entry.bind("<Return>", lambda _event: self._connect_from_form())
        self.username_entry.focus_set()

    def _build_chat(self) -> None:
        self.login_frame.destroy()
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        layout = ttk.Panedwindow(self.root, orient="horizontal")
        layout.grid(row=0, column=0, sticky="nsew")
        sidebar = ttk.Frame(layout, padding=12)
        conversation = ttk.Frame(layout, padding=12)
        layout.add(sidebar, weight=1)
        layout.add(conversation, weight=4)

        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(3, weight=1)
        ttk.Label(sidebar, text=f"Conectado como {self.username}").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        ttk.Label(sidebar, text="Salas").grid(row=1, column=0, sticky="w")

        room_form = ttk.Frame(sidebar)
        room_form.grid(row=2, column=0, sticky="ew", pady=(6, 8))
        room_form.columnconfigure(0, weight=1)
        self.room_entry = ttk.Entry(room_form)
        self.room_entry.grid(row=0, column=0, sticky="ew")
        self.room_entry.insert(0, "nombre-sala")
        self.room_entry.bind("<FocusIn>", self._clear_room_hint)
        self.room_entry.bind("<Return>", lambda _event: self._create_room())
        ttk.Button(room_form, text="Crear sala", command=self._create_room).grid(
            row=1, column=0, sticky="ew", pady=(5, 0)
        )

        room_list_frame = ttk.Frame(sidebar)
        room_list_frame.grid(row=3, column=0, sticky="nsew")
        room_list_frame.columnconfigure(0, weight=1)
        room_list_frame.rowconfigure(0, weight=1)
        self.room_list = tk.Listbox(
            room_list_frame,
            exportselection=False,
            activestyle="underline",
            height=12,
            font=("Segoe UI", self.text_size),
            selectmode=tk.SINGLE,
        )
        room_scroll = ttk.Scrollbar(
            room_list_frame,
            orient="vertical",
            command=self.room_list.yview,
        )
        self.room_list.configure(yscrollcommand=room_scroll.set)
        self.room_list.grid(row=0, column=0, sticky="nsew")
        room_scroll.grid(row=0, column=1, sticky="ns")
        self.room_list.bind("<<ListboxSelect>>", self._select_room)
        self.room_list.bind("<Return>", lambda _event: self._join_room())

        room_actions = ttk.Frame(sidebar)
        room_actions.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        room_actions.columnconfigure(0, weight=1)
        room_actions.columnconfigure(1, weight=1)
        self.join_button = ttk.Button(
            room_actions,
            text="Unirse",
            command=self._join_room,
        )
        self.join_button.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=3)
        self.leave_button = ttk.Button(
            room_actions,
            text="Salir de sala",
            command=self._leave_room,
        )
        self.leave_button.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=3)
        ttk.Button(
            room_actions,
            text="Actualizar salas",
            command=self._refresh_rooms,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=3)
        ttk.Button(
            room_actions,
            text="Ver integrantes",
            command=self._list_members,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=3)
        self.delete_room_button = ttk.Button(
            room_actions,
            text="Eliminar sala",
            command=self._delete_room,
        )
        self.delete_room_button.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=3,
        )

        conversation.columnconfigure(0, weight=1)
        conversation.rowconfigure(1, weight=1)
        header = ttk.Frame(conversation)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        self.room_title = tk.StringVar(value="Selecciona una sala")
        ttk.Label(
            header,
            textvariable=self.room_title,
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.members_var = tk.StringVar(value="Elige una sala y únete para conversar.")
        ttk.Label(header, textvariable=self.members_var).grid(
            row=1, column=0, sticky="w", pady=(3, 0)
        )
        font_controls = ttk.Frame(header)
        font_controls.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(
            font_controls,
            text="A−",
            width=4,
            command=lambda: self._change_text_size(-1),
        ).grid(row=0, column=0, padx=2)
        ttk.Button(
            font_controls,
            text="A+",
            width=4,
            command=lambda: self._change_text_size(1),
        ).grid(row=0, column=1, padx=2)
        ttk.Label(font_controls, text="Tamaño del texto").grid(
            row=1, column=0, columnspan=2
        )

        chat_frame = ttk.Frame(conversation)
        chat_frame.grid(row=1, column=0, sticky="nsew")
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)
        self.chat_font = tkfont.Font(
            root=self.root,
            family="Segoe UI",
            size=self.text_size,
        )
        self.chat_display = tk.Text(
            chat_frame,
            wrap="word",
            state="disabled",
            font=self.chat_font,
            background="white",
            foreground="black",
            padx=12,
            pady=12,
            spacing1=3,
            spacing3=8,
            takefocus=True,
        )
        chat_scroll = ttk.Scrollbar(
            chat_frame,
            orient="vertical",
            command=self.chat_display.yview,
        )
        self.chat_display.configure(yscrollcommand=chat_scroll.set)
        self.chat_display.grid(row=0, column=0, sticky="nsew")
        chat_scroll.grid(row=0, column=1, sticky="ns")
        self.chat_display.tag_configure("sender", font=("Segoe UI", self.text_size, "bold"))
        self.chat_display.tag_configure("system", foreground="#333333")

        composer_frame = ttk.Frame(conversation)
        composer_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        composer_frame.columnconfigure(0, weight=1)
        ttk.Label(composer_frame, text="Mensaje (Ctrl+Enter para enviar):").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        self.composer = tk.Text(
            composer_frame,
            height=3,
            wrap="word",
            font=self.chat_font,
            background="white",
            foreground="black",
            takefocus=True,
        )
        self.composer.grid(row=1, column=0, sticky="ew")
        self.composer.bind("<Control-Return>", self._send_from_shortcut)
        self.send_button = ttk.Button(
            composer_frame,
            text="Enviar",
            command=self._send_message,
        )
        self.send_button.grid(row=1, column=1, sticky="ns", padx=(8, 0))
        self.root.bind_all("<Control-r>", lambda _event: self._refresh_rooms())
        self.root.bind_all("<Control-l>", self._focus_composer)
        self.status_var.set("Conectado. Selecciona o crea una sala.")
        self._update_room_actions()
        self._show_chat_text("Selecciona una sala de la lista para comenzar.")
        self._refresh_rooms()

    def _connect_from_form(self) -> None:
        username = self.username_entry.get().strip()
        host = self.host_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.status_var.set("El puerto debe ser un número entre 1 y 65535.")
            self.port_entry.focus_set()
            return
        if not username or not host:
            self.status_var.set("Completa el usuario y el servidor.")
            return
        self.connect_button.configure(state="disabled")
        self.status_var.set("Conectando al servidor…")
        self._submit(self._connect(host, port, username), "connect")

    def _create_room(self) -> None:
        room = self.room_entry.get().strip().lower()
        if room and room != "nombre-sala":
            self.room_entry.delete(0, tk.END)
            self.room_entry.insert(0, room)
            self._submit(self._request("CREATE_ROOM", room=room), "create")
        else:
            self.status_var.set("Escribe el nombre de la sala que quieres crear.")
            self.room_entry.focus_set()

    def _clear_room_hint(self, _event: tk.Event[Any]) -> None:
        if self.room_entry.get() == "nombre-sala":
            self.room_entry.delete(0, tk.END)

    def _selected_room_name(self) -> str | None:
        selection = self.room_list.curselection()
        if not selection:
            return None
        index = selection[0]
        if index >= len(self.room_names):
            return None
        return self.room_names[index]

    def _select_room(self, _event: tk.Event[Any] | None = None) -> None:
        room = self._selected_room_name()
        if room is None:
            return
        self.selected_room = room
        self.room_title.set(f"# {room}")
        if room in self.joined_rooms:
            self.members_var.set("Ya formas parte de esta sala.")
            self._render_messages(room)
        else:
            self.members_var.set("Sala disponible. Pulsa «Unirse» para conversar.")
            self._show_chat_text(f"Únete a #{room} para ver y enviar mensajes.")
        self._update_room_actions()

    def _join_room(self) -> None:
        room = self._selected_room_name()
        if room is None:
            self.status_var.set("Selecciona una sala de la lista.")
        elif room in self.joined_rooms:
            self.status_var.set(f"Ya formas parte de #{room}.")
        else:
            self._submit(self._request("JOIN_ROOM", room=room), "join")

    def _leave_room(self) -> None:
        room = self._selected_room_name()
        if room is None or room not in self.joined_rooms:
            self.status_var.set("Selecciona una sala a la que ya te hayas unido.")
            return
        self._submit(self._request("LEAVE_ROOM", room=room), "leave")

    def _delete_room(self) -> None:
        room = self._selected_room_name()
        if room is None or self.room_owners.get(room) != self.username:
            self.status_var.set("Solo quien creó la sala puede eliminarla.")
            return
        confirmed = messagebox.askyesno(
            "Eliminar sala",
            f"¿Eliminar #{room}, su historial y retirar a todos sus integrantes?",
            parent=self.root,
        )
        if confirmed:
            self._submit(self._request("DELETE_ROOM", room=room), "delete")

    def _refresh_rooms(self) -> None:
        if self.client is not None:
            self._submit(self._request("LIST_ROOMS"), "rooms")

    def _list_members(self) -> None:
        room = self._selected_room_name()
        if room is None:
            self.status_var.set("Selecciona una sala para consultar sus integrantes.")
            return
        self._submit(self._request("LIST_USERS", room=room), "members")

    def _send_from_shortcut(self, _event: tk.Event[Any]) -> str:
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        room = self.selected_room
        if room is None or room not in self.joined_rooms:
            self.status_var.set("Únete a una sala antes de enviar mensajes.")
            return
        if self._sending:
            return
        content = self.composer.get("1.0", "end-1c")
        if not content.strip():
            self.status_var.set("Escribe un mensaje antes de enviarlo.")
            self.composer.focus_set()
            return
        self._sending = True
        self.send_button.configure(state="disabled")
        self._submit(
            self._request("SEND_MESSAGE", room=room, content=content),
            "send",
        )

    def _change_text_size(self, change: int) -> None:
        self.text_size = min(24, max(10, self.text_size + change))
        self.chat_font.configure(size=self.text_size)
        self.room_list.configure(font=("Segoe UI", self.text_size))
        self.chat_display.tag_configure(
            "sender",
            font=("Segoe UI", self.text_size, "bold"),
        )

    def _focus_composer(self, _event: tk.Event[Any]) -> str:
        if hasattr(self, "composer") and str(self.composer["state"]) != "disabled":
            self.composer.focus_set()
        return "break"

    def _update_room_actions(self) -> None:
        room = self.selected_room
        joined = room is not None and room in self.joined_rooms
        self.join_button.configure(state="disabled" if joined or room is None else "normal")
        self.leave_button.configure(state="normal" if joined else "disabled")
        is_owner = room is not None and self.room_owners.get(room) == self.username
        self.delete_room_button.configure(state="normal" if is_owner else "disabled")
        self.composer.configure(state="normal" if joined else "disabled")
        self.send_button.configure(
            state="normal" if joined and not self._sending else "disabled"
        )

    def _show_chat_text(self, text: str) -> None:
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.insert(tk.END, text, "system")
        self.chat_display.configure(state="disabled")

    def _render_messages(self, room: str) -> None:
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", tk.END)
        messages = self.messages.get(room, {})
        for message in sorted(messages.values(), key=lambda item: item["timestamp"]):
            timestamp = self._format_time(message["timestamp"])
            self.chat_display.insert(
                tk.END,
                f"{timestamp} · {message['username']}\n",
                "sender",
            )
            self.chat_display.insert(tk.END, f"{message['content']}\n\n")
        if not messages:
            self.chat_display.insert(
                tk.END,
                "Todavía no hay mensajes en esta sala.\n",
                "system",
            )
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)

    @staticmethod
    def _format_time(timestamp: str) -> str:
        try:
            parsed = timestamp.replace("Z", "+00:00")
            return datetime.fromisoformat(parsed).astimezone().strftime("%H:%M")
        except ValueError:
            return timestamp

    def _process_ui_events(self) -> None:
        while True:
            try:
                kind, action, payload = self.ui_events.get_nowait()
            except queue.Empty:
                break
            if kind == "result":
                self._handle_result(action, payload)
            elif kind == "error":
                self._handle_error(action, payload)
            elif kind == "event":
                self._handle_server_event(payload)
            elif kind == "closed":
                self.root.destroy()
                return
        self.root.after(50, self._process_ui_events)

    def _handle_result(self, action: str, response: dict[str, Any]) -> None:
        if action == "connect":
            if response.get("type") == "ERROR":
                self.status_var.set(response.get("message", "No se pudo conectar."))
                self.connect_button.configure(state="normal")
                return
            self._build_chat()
            return

        if action == "send":
            self._sending = False
            self.send_button.configure(
                state="normal" if self.selected_room in self.joined_rooms else "disabled"
            )
            if response.get("type") == "SUCCESS":
                self.composer.delete("1.0", tk.END)
                self.status_var.set("Mensaje enviado.")
            else:
                self.status_var.set(response.get("message", "No se pudo enviar el mensaje."))
            return

        if response.get("type") == "ERROR":
            self.status_var.set(response.get("message", "La operación no se pudo completar."))
            return

        data = response.get("data", {})
        if action == "rooms":
            rooms = data.get("rooms", [])
            self.room_names = [item["room"] for item in rooms]
            self.room_owners = {
                item["room"]: item["created_by"]
                for item in rooms
            }
            self.room_list.delete(0, tk.END)
            for item in rooms:
                room = item["room"]
                membership = " (unido)" if room in self.joined_rooms else ""
                self.room_list.insert(
                    tk.END,
                    f"# {room}  ·  {item['members_count']} integrantes{membership}",
                )
            if self.selected_room in self.room_names:
                index = self.room_names.index(self.selected_room)
                self.room_list.selection_set(index)
                self.room_list.activate(index)
                self._select_room()
            elif self.room_names:
                self.room_list.selection_set(0)
                self.room_list.activate(0)
                self._select_room()
            self.status_var.set(f"Salas actualizadas ({len(rooms)}).")
        elif action == "create":
            room = data.get("room")
            if room:
                self.joined_rooms.add(room)
                self.selected_room = room
                self.status_var.set(f"Sala #{room} creada; ya formas parte de ella.")
                self._refresh_rooms()
                self._load_history(room)
        elif action == "join":
            room = data.get("room")
            if room:
                self.joined_rooms.add(room)
                self.selected_room = room
                self.status_var.set(f"Te uniste a #{room}.")
                self._refresh_rooms()
                self._load_history(room)
            self._select_room_by_name(room)
        elif action == "leave":
            room = data.get("room")
            if room:
                self.joined_rooms.discard(room)
                self.status_var.set(f"Saliste de #{room}.")
                if self.selected_room == room:
                    self._select_room_by_name(room)
                self._refresh_rooms()
        elif action == "delete":
            room = data.get("room")
            if room:
                self._remove_deleted_room(room)
                self.status_var.set(f"Sala #{room} y su historial eliminados.")
        elif action == "history":
            room = response.get("room")
            if room:
                for message in response.get("messages", []):
                    self._store_message(message)
                if self.selected_room == room:
                    self._render_messages(room)
                notice = " El historial fue limitado por el tamaño del protocolo." if response.get(
                    "truncated"
                ) else ""
                self.status_var.set(f"Historial de #{room} cargado.{notice}")
        elif action == "members":
            users = data.get("users", [])
            room = self.selected_room or ""
            self.members_var.set(f"Integrantes de #{room}: {', '.join(users) or 'ninguno'}")

    def _select_room_by_name(self, room: str | None) -> None:
        if room is None or room not in self.room_names:
            self._update_room_actions()
            return
        index = self.room_names.index(room)
        self.room_list.selection_clear(0, tk.END)
        self.room_list.selection_set(index)
        self.room_list.activate(index)
        self._select_room()

    def _load_history(self, room: str) -> None:
        self._submit(self._request("HISTORY", room=room), "history")
        self._update_room_actions()
        self._select_room_by_name(room)

    def _store_message(self, message: dict[str, str]) -> None:
        room = message["room"]
        key = (message["timestamp"], message["username"], message["content"])
        self.messages.setdefault(room, {})[key] = message

    def _remove_deleted_room(self, room: str) -> None:
        self.joined_rooms.discard(room)
        self.messages.pop(room, None)
        self.room_owners.pop(room, None)
        if self.selected_room == room:
            self.selected_room = None
            self.room_title.set("Selecciona una sala")
            self.members_var.set("")
            self._show_chat_text(f"La sala #{room} fue eliminada.")
        self._update_room_actions()
        self._refresh_rooms()

    def _handle_server_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "CHAT_MESSAGE":
            self._store_message(event)
            room = event["room"]
            if self.selected_room == room:
                self._render_messages(room)
                self.status_var.set(f"Nuevo mensaje en #{room}.")
            else:
                self.status_var.set(f"Nuevo mensaje en #{room}.")
        elif event_type in {"ROOM_CREATED", "USER_JOINED", "USER_LEFT"}:
            room = event.get("room", "")
            self._refresh_rooms()
            if event_type == "ROOM_CREATED":
                self.status_var.set(f"{event.get('created_by', 'Un usuario')} creó #{room}.")
            elif event_type == "USER_JOINED":
                self.status_var.set(f"{event.get('username', 'Un usuario')} se unió a #{room}.")
            else:
                self.status_var.set(f"{event.get('username', 'Un usuario')} salió de #{room}.")
        elif event_type == "ROOM_DELETED":
            room = event.get("room", "")
            self._remove_deleted_room(room)
            self.status_var.set(f"{event.get('deleted_by', 'Un usuario')} eliminó #{room}.")
        elif event_type == "USER_CONNECTED":
            self.status_var.set(f"{event.get('username', 'Un usuario')} se conectó.")
        elif event_type == "USER_DISCONNECTED":
            self.status_var.set(f"{event.get('username', 'Un usuario')} se desconectó.")

    def _handle_error(self, action: str, error: str) -> None:
        if action == "connect":
            self.connect_button.configure(state="normal")
        if action == "send":
            self._sending = False
            self._update_room_actions()
        self.status_var.set(f"No se pudo completar la operación: {error}")

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self.client is None:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.root.destroy()
            return

        async def shutdown() -> None:
            if self.client is not None:
                await self.client.close()
                self.client = None
            current = asyncio.current_task()
            pending = [
                task for task in asyncio.all_tasks()
                if task is not current
            ]
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        future = asyncio.run_coroutine_threadsafe(shutdown(), self.loop)

        def finished(result: Future[None]) -> None:
            try:
                result.result()
            except Exception as error:
                self.ui_events.put(("error", "shutdown", str(error)))
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.ui_events.put(("closed", "", None))

        future.add_done_callback(finished)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interfaz accesible de ChatRoom")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = tk.Tk()
    ChatRoomApp(root, args.host, args.port)
    root.mainloop()


if __name__ == "__main__":
    main()

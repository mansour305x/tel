import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.config import BotConfig
from bot.security import sanitize_text

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def now_iso() -> str:
    return datetime.utcnow().isoformat(sep=" ", timespec="seconds")


async def initialize_database(config: BotConfig) -> None:
    async with aiosqlite.connect(config.database_path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, role TEXT DEFAULT 'user', created_at TEXT, updated_at TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS admin_users (user_id INTEGER PRIMARY KEY, created_at TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS ui_texts (key TEXT PRIMARY KEY, value TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS ui_buttons (key TEXT PRIMARY KEY, label TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS templates (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, label TEXT, description TEXT, category TEXT, visible INTEGER DEFAULT 1, requires_subbot INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, location TEXT, action_type TEXT, action_value TEXT, position INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT, message TEXT, created_at TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS support_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, message TEXT, status TEXT DEFAULT 'open', created_at TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS bot_projects (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, bot_username TEXT, bot_name TEXT, bot_token TEXT, template TEXT, status TEXT DEFAULT 'stopped', created_at TEXT, updated_at TEXT)")

        await conn.commit()

        await _seed_defaults(conn, config)


async def _seed_defaults(conn: aiosqlite.Connection, config: BotConfig) -> None:
    default_texts_path = DATA_DIR / "texts.json"
    default_buttons_path = DATA_DIR / "buttons.json"
    if default_texts_path.exists():
        with open(default_texts_path, "r", encoding="utf-8") as fp:
            default_texts = json.load(fp)
    else:
        default_texts = {}

    if default_buttons_path.exists():
        with open(default_buttons_path, "r", encoding="utf-8") as fp:
            default_buttons = json.load(fp)
    else:
        default_buttons = {}

    for key, value in default_texts.items():
        await conn.execute("INSERT OR IGNORE INTO ui_texts (key, value) VALUES (?, ?)", (key, sanitize_text(value)))

    for key, label in default_buttons.items():
        await conn.execute("INSERT OR IGNORE INTO ui_buttons (key, label) VALUES (?, ?)", (key, sanitize_text(label)))

    await conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")

    for admin_id in config.admin_ids:
        await conn.execute("INSERT OR IGNORE INTO admin_users (user_id, created_at) VALUES (?, ?)", (admin_id, now_iso()))

    await conn.commit()


async def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    raise NotImplementedError("Use specific helper functions")


async def get_text(key: str) -> str:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT value FROM ui_texts WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else ""


async def set_text(key: str, value: str) -> None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute("INSERT INTO ui_texts (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, sanitize_text(value)))
        await conn.commit()


async def get_button_label(key: str) -> str:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT label FROM ui_buttons WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else key


async def create_template(key: str, label: str, description: str, category: str, visible: bool, requires_subbot: bool) -> int:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        cur = await conn.execute(
            "INSERT INTO templates (key, label, description, category, visible, requires_subbot, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, sanitize_text(label), sanitize_text(description), sanitize_text(category), int(visible), int(requires_subbot), 1, now_iso(), now_iso())
        )
        await conn.commit()
        return cur.lastrowid


async def update_template(template_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = tuple(sanitize_text(str(value)) for value in fields.values())
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute(f"UPDATE templates SET {columns}, updated_at = ? WHERE id = ?", (*values, now_iso(), template_id))
        await conn.commit()


async def delete_template(template_id: int) -> None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        await conn.commit()


async def list_templates(active_only: bool = True) -> list[dict[str, Any]]:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        if active_only:
            cur = await conn.execute("SELECT * FROM templates WHERE active = 1 ORDER BY created_at DESC")
        else:
            cur = await conn.execute("SELECT * FROM templates ORDER BY created_at DESC")
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def get_template(template_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_button(name: str, location: str, action_type: str, action_value: str, position: int) -> int:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        cur = await conn.execute(
            "INSERT INTO buttons (name, location, action_type, action_value, position, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (sanitize_text(name), sanitize_text(location), sanitize_text(action_type), sanitize_text(action_value), position, now_iso(), now_iso())
        )
        await conn.commit()
        return cur.lastrowid


async def update_button(button_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = tuple(sanitize_text(str(value)) for value in fields.values())
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute(f"UPDATE buttons SET {columns}, updated_at = ? WHERE id = ?", (*values, now_iso(), button_id))
        await conn.commit()


async def delete_button(button_id: int) -> None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute("DELETE FROM buttons WHERE id = ?", (button_id,))
        await conn.commit()


async def list_buttons(active_only: bool = True, location: str | None = None) -> list[dict[str, Any]]:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        query = "SELECT * FROM buttons"
        params: tuple[Any, ...] = ()
        if active_only and location:
            query += " WHERE active = 1 AND location = ?"
            params = (location,)
        elif active_only:
            query += " WHERE active = 1"
        if location is None:
            query += " ORDER BY position, id"
        else:
            query += " ORDER BY position, id"
        cur = await conn.execute(query, params)
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def get_button(button_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM buttons WHERE id = ?", (button_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_log(level: str, message: str) -> None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute("INSERT INTO logs (level, message, created_at) VALUES (?, ?, ?)", (level, sanitize_text(message), now_iso()))
        await conn.commit()


async def get_logs(limit: int = 20) -> list[dict[str, Any]]:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def get_support_messages(limit: int = 20) -> list[dict[str, Any]]:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM support_messages ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def register_user(user_id: int, username: str | None, full_name: str | None, role: str = "user") -> None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username, full_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, full_name = excluded.full_name, role = excluded.role, updated_at = excluded.updated_at",
            (user_id, username or "", full_name or "", role, now_iso(), now_iso())
        )
        await conn.commit()


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [row[0] for row in rows]


async def get_setting(key: str) -> str | None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
        await conn.commit()


async def create_project(owner_id: int, bot_username: str, bot_name: str, bot_token: str, template: str) -> int:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        cur = await conn.execute(
            "INSERT INTO bot_projects (owner_id, bot_username, bot_name, bot_token, template, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_id, sanitize_text(bot_username), sanitize_text(bot_name), bot_token, sanitize_text(template), "stopped", now_iso(), now_iso())
        )
        await conn.commit()
        return cur.lastrowid


async def update_project(project_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = tuple(sanitize_text(str(value)) if isinstance(value, str) else value for value in fields.values())
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        await conn.execute(f"UPDATE bot_projects SET {columns}, updated_at = ? WHERE id = ?", (*values, now_iso(), project_id))
        await conn.commit()


async def list_user_projects(owner_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM bot_projects WHERE owner_id = ? ORDER BY id DESC", (owner_id,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def get_project(project_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(BotConfig().database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM bot_projects WHERE id = ?", (project_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def all_templates() -> list[dict[str, Any]]:
    return await list_templates(active_only=True)


async def all_buttons() -> list[dict[str, Any]]:
    return await list_buttons(active_only=True)

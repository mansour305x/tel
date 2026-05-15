import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VALID_CATEGORIES = {
    "متجر",
    "دعم فني",
    "طلبات",
    "اشتراكات",
    "ردود تلقائية",
    "حجوزات",
    "تصويت",
    "كورسات",
    "كوبونات",
    "تتبع طلبات",
    "قالب مخصص",
}

VALID_LOCATIONS = {
    "main_menu",
    "owner_menu",
    "templates",
    "my_bots",
    "support",
    "subscriptions",
}

VALID_ACTION_TYPES = {
    "message",
    "url",
    "menu",
    "template",
    "support",
    "project_start",
    "project_stop",
    "project_restart",
    "stats",
    "broadcast",
    "setting_toggle",
}


def load_actions() -> dict[str, str]:
    path = DATA_DIR / "actions.json"
    if not path.exists():
        return {name: name for name in VALID_ACTION_TYPES}
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return {item["type"]: item["label"] for item in data}

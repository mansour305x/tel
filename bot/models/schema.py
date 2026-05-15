from dataclasses import dataclass


@dataclass
class TemplateEntry:
    id: int
    key: str
    label: str
    description: str
    category: str
    visible: bool
    requires_subbot: bool
    active: bool
    created_at: str
    updated_at: str


@dataclass
class ButtonEntry:
    id: int
    name: str
    location: str
    action_type: str
    action_value: str
    position: int
    active: bool
    created_at: str
    updated_at: str


@dataclass
class ProjectEntry:
    id: int
    owner_id: int
    bot_username: str
    bot_name: str
    bot_token: str
    template: str
    status: str
    created_at: str
    updated_at: str

from __future__ import annotations

from pydantic import BaseModel, Field


class AreaInfo(BaseModel):
    area_id: str
    name: str
    floor_id: str | None = None
    labels: list[str] = Field(default_factory=list)


class DeviceInfo(BaseModel):
    device_id: str = Field(alias="id")
    name: str | None = None
    name_by_user: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    area_id: str | None = None
    labels: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @property
    def display_name(self) -> str:
        return self.name_by_user or self.name or self.device_id


class EntityRegistryEntry(BaseModel):
    entity_id: str
    name: str | None = None
    original_name: str | None = None
    platform: str | None = None
    device_id: str | None = None
    area_id: str | None = None
    labels: list[str] = Field(default_factory=list)
    disabled_by: str | None = None
    hidden_by: str | None = None
    entity_category: str | None = None
    device_class: str | None = None
    original_device_class: str | None = None


class EntityState(BaseModel):
    entity_id: str
    state: str
    attributes: dict = Field(default_factory=dict)
    last_changed: str | None = None
    last_updated: str | None = None


class EntitySummary(BaseModel):
    entity_id: str
    domain: str
    friendly_name: str | None = None
    device_class: str | None = None
    area: str | None = None
    state: str | None = None
    platform: str | None = None


class EntityDetail(BaseModel):
    entity_id: str
    domain: str
    friendly_name: str | None = None
    device_class: str | None = None
    area: str | None = None
    state: str | None = None
    attributes: dict = Field(default_factory=dict)
    last_changed: str | None = None
    last_updated: str | None = None
    platform: str | None = None
    device_name: str | None = None
    device_manufacturer: str | None = None
    device_model: str | None = None
    entity_category: str | None = None
    labels: list[str] = Field(default_factory=list)
    disabled_by: str | None = None
    hidden_by: str | None = None


class DomainSummary(BaseModel):
    domain: str
    entity_count: int
    sample_entities: list[str] = Field(default_factory=list)


class IntegrationSummary(BaseModel):
    integration: str
    entity_count: int
    sample_entities: list[str] = Field(default_factory=list)


class ServiceField(BaseModel):
    name: str
    description: str | None = None
    required: bool = False
    example: str | None = None
    selector: dict | None = None


class ServiceInfo(BaseModel):
    domain: str
    service: str
    name: str | None = None
    description: str | None = None
    fields: list[ServiceField] = Field(default_factory=list)


class EntityReference(BaseModel):
    entity_id: str
    exists: bool
    file: str
    line: int
    friendly_name: str | None = None


class CoreConfig(BaseModel):
    version: str | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    time_zone: str | None = None
    unit_system: dict | None = None
    components: list[str] = Field(default_factory=list)
    config_dir: str | None = None
    external_url: str | None = None
    internal_url: str | None = None
    currency: str | None = None
    country: str | None = None
    language: str | None = None
    safe_mode: bool | None = None
    state: str | None = None


class Panel(BaseModel):
    component_name: str | None = None
    url_path: str
    title: str | None = None
    icon: str | None = None
    require_admin: bool = False
    config_panel_domain: str | None = None


class ConfigEntry(BaseModel):
    entry_id: str
    domain: str
    title: str | None = None
    state: str | None = None
    source: str | None = None
    disabled_by: str | None = None
    pref_disable_polling: bool | None = None
    pref_disable_new_entities: bool | None = None
    supports_options: bool | None = None
    supports_remove_device: bool | None = None
    supports_unload: bool | None = None
    reason: str | None = None


class Label(BaseModel):
    label_id: str
    name: str
    color: str | None = None
    icon: str | None = None
    description: str | None = None


class Floor(BaseModel):
    floor_id: str
    name: str
    level: int | None = None
    icon: str | None = None
    aliases: list[str] = Field(default_factory=list)


class Category(BaseModel):
    category_id: str
    scope: str
    name: str
    icon: str | None = None


class HistoryPoint(BaseModel):
    entity_id: str
    state: str | None = None
    last_changed: str | None = None
    last_updated: str | None = None
    attributes: dict | None = None


class LogbookEntry(BaseModel):
    when: str | float | None = None
    name: str | None = None
    message: str | None = None
    entity_id: str | None = None
    domain: str | None = None
    context_id: str | None = None
    context_user_id: str | None = None
    context_event_type: str | None = None
    state: str | None = None
    icon: str | None = None
    source: str | None = None


class Repair(BaseModel):
    issue_id: str
    domain: str | None = None
    severity: str | None = None
    breaks_in_ha_version: str | None = None
    created: str | None = None
    is_fixable: bool | None = None
    is_persistent: bool | None = None
    learn_more_url: str | None = None
    translation_key: str | None = None
    translation_placeholders: dict | None = None
    ignored: bool | None = None
    dismissed_version: str | None = None


class Notification(BaseModel):
    notification_id: str
    title: str | None = None
    message: str | None = None
    created_at: str | None = None
    status: str | None = None


class CalendarEvent(BaseModel):
    start: dict | str | None = None
    end: dict | str | None = None
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    uid: str | None = None
    recurrence_id: str | None = None

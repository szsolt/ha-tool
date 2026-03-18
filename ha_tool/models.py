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

from __future__ import annotations

import fnmatch
import re
from collections import defaultdict

from ha_tool.models import (
    AreaInfo,
    DeviceInfo,
    DomainSummary,
    EntityDetail,
    EntityReference,
    EntityRegistryEntry,
    EntityState,
    EntitySummary,
    IntegrationSummary,
    ServiceField,
    ServiceInfo,
)


class EntityIndex:
    def __init__(
        self,
        states: list[dict],
        entity_entries: list[dict],
        device_entries: list[dict],
        area_entries: list[dict],
        services_raw: dict | None = None,
    ) -> None:
        self._areas: dict[str, AreaInfo] = {}
        self._devices: dict[str, DeviceInfo] = {}
        self._registry: dict[str, EntityRegistryEntry] = {}
        self._states: dict[str, EntityState] = {}
        self._services_raw = services_raw

        for raw in area_entries:
            area = AreaInfo.model_validate(raw)
            self._areas[area.area_id] = area

        for raw in device_entries:
            dev = DeviceInfo.model_validate(raw)
            self._devices[dev.device_id] = dev

        for raw in entity_entries:
            entry = EntityRegistryEntry.model_validate(raw)
            self._registry[entry.entity_id] = entry

        for raw in states:
            st = EntityState.model_validate(raw)
            self._states[st.entity_id] = st

    def _resolve_area(self, entity_id: str) -> str | None:
        reg = self._registry.get(entity_id)
        if not reg:
            return None

        area_id = reg.area_id
        if not area_id and reg.device_id:
            dev = self._devices.get(reg.device_id)
            if dev:
                area_id = dev.area_id

        if area_id:
            area = self._areas.get(area_id)
            return area.name if area else area_id
        return None

    def _resolve_device_class(self, entity_id: str) -> str | None:
        reg = self._registry.get(entity_id)
        if reg:
            dc = reg.device_class or reg.original_device_class
            if dc:
                return dc

        st = self._states.get(entity_id)
        if st:
            return st.attributes.get("device_class")
        return None

    def _resolve_friendly_name(self, entity_id: str) -> str | None:
        reg = self._registry.get(entity_id)
        if reg and reg.name:
            return reg.name
        if reg and reg.original_name:
            return reg.original_name

        st = self._states.get(entity_id)
        if st:
            return st.attributes.get("friendly_name")
        return None

    def _domain(self, entity_id: str) -> str:
        return entity_id.split(".", 1)[0]

    def to_summary(self, entity_id: str) -> EntitySummary:
        reg = self._registry.get(entity_id)
        st = self._states.get(entity_id)
        return EntitySummary(
            entity_id=entity_id,
            domain=self._domain(entity_id),
            friendly_name=self._resolve_friendly_name(entity_id),
            device_class=self._resolve_device_class(entity_id),
            area=self._resolve_area(entity_id),
            state=st.state if st else None,
            platform=reg.platform if reg else None,
        )

    def to_detail(self, entity_id: str) -> EntityDetail:
        reg = self._registry.get(entity_id)
        st = self._states.get(entity_id)
        dev: DeviceInfo | None = None
        if reg and reg.device_id:
            dev = self._devices.get(reg.device_id)

        return EntityDetail(
            entity_id=entity_id,
            domain=self._domain(entity_id),
            friendly_name=self._resolve_friendly_name(entity_id),
            device_class=self._resolve_device_class(entity_id),
            area=self._resolve_area(entity_id),
            state=st.state if st else None,
            attributes=st.attributes if st else {},
            last_changed=st.last_changed if st else None,
            last_updated=st.last_updated if st else None,
            platform=reg.platform if reg else None,
            device_name=dev.display_name if dev else None,
            device_manufacturer=dev.manufacturer if dev else None,
            device_model=dev.model if dev else None,
            entity_category=reg.entity_category if reg else None,
            labels=reg.labels if reg else [],
            disabled_by=reg.disabled_by if reg else None,
            hidden_by=reg.hidden_by if reg else None,
        )

    @property
    def all_entity_ids(self) -> list[str]:
        return sorted(set(self._registry.keys()) | set(self._states.keys()))

    @staticmethod
    def _build_text_matcher(text: str) -> tuple[re.Pattern[str], bool]:
        """Build a matcher from text input.

        Auto-detects the matching strategy:
        - Contains unescaped regex metacharacters (^$|+(){}[]) → regex
        - Contains glob wildcards (* or ?) → glob (anchored full-match per field)
        - Otherwise → substring match

        Returns (pattern, is_glob) — glob patterns match per-field,
        substring/regex patterns match against the concatenated searchable string.
        """
        regex_meta = re.compile(r'(?<!\\)[\^$|+(){}\[\]]')
        if regex_meta.search(text):
            return re.compile(text, re.IGNORECASE), False

        if "*" in text or "?" in text:
            pattern = fnmatch.translate(text)
            return re.compile(pattern, re.IGNORECASE), True

        return re.compile(re.escape(text), re.IGNORECASE), False

    def search(
        self,
        text: str | None = None,
        domain: str | None = None,
        device_class: str | None = None,
        area: str | None = None,
        integration: str | None = None,
        include_disabled: bool = False,
    ) -> list[EntitySummary]:
        results: list[EntitySummary] = []
        text_matcher: re.Pattern[str] | None = None
        is_glob = False
        if text:
            text_matcher, is_glob = self._build_text_matcher(text)
        area_lower = area.lower() if area else None

        for eid in self.all_entity_ids:
            reg = self._registry.get(eid)

            if not include_disabled and reg and reg.disabled_by:
                continue

            if domain and self._domain(eid) != domain:
                continue

            dc = self._resolve_device_class(eid)
            if device_class and (dc or "").lower() != device_class.lower():
                continue

            resolved_area = self._resolve_area(eid)
            if area_lower and (not resolved_area or area_lower not in resolved_area.lower()):
                continue

            if integration and (not reg or (reg.platform or "").lower() != integration.lower()):
                continue

            if text_matcher:
                friendly = self._resolve_friendly_name(eid) or ""
                if is_glob:
                    # Glob: full-match against each field individually
                    if not (
                        text_matcher.match(eid)
                        or text_matcher.match(friendly)
                        or (resolved_area and text_matcher.match(resolved_area))
                    ):
                        continue
                else:
                    # Regex/substring: search within concatenated string
                    searchable = f"{eid} {friendly} {resolved_area or ''}"
                    if not text_matcher.search(searchable):
                        continue

            results.append(self.to_summary(eid))

        return results

    def inspect(self, entity_ids: list[str]) -> list[EntityDetail]:
        results: list[EntityDetail] = []
        for eid in entity_ids:
            if eid in self._registry or eid in self._states:
                results.append(self.to_detail(eid))
        return results

    def get_state(self, entity_id: str) -> dict | None:
        st = self._states.get(entity_id)
        if not st:
            return None
        return {
            "entity_id": entity_id,
            "state": st.state,
            "friendly_name": self._resolve_friendly_name(entity_id),
            "last_changed": st.last_changed,
        }

    def list_areas(self) -> list[AreaInfo]:
        return sorted(self._areas.values(), key=lambda a: a.name)

    def list_domains(self) -> list[DomainSummary]:
        domain_entities: dict[str, list[str]] = defaultdict(list)
        for eid in self.all_entity_ids:
            reg = self._registry.get(eid)
            if reg and reg.disabled_by:
                continue
            d = self._domain(eid)
            domain_entities[d].append(eid)

        results: list[DomainSummary] = []
        for d in sorted(domain_entities):
            eids = domain_entities[d]
            results.append(
                DomainSummary(
                    domain=d,
                    entity_count=len(eids),
                    sample_entities=eids[:5],
                )
            )
        return results

    def list_integrations(self) -> list[IntegrationSummary]:
        integration_entities: dict[str, list[str]] = defaultdict(list)
        for eid in self.all_entity_ids:
            reg = self._registry.get(eid)
            if reg and reg.disabled_by:
                continue
            platform = reg.platform if reg else None
            if platform:
                integration_entities[platform].append(eid)

        results: list[IntegrationSummary] = []
        for integ in sorted(integration_entities):
            eids = integration_entities[integ]
            results.append(
                IntegrationSummary(
                    integration=integ,
                    entity_count=len(eids),
                    sample_entities=eids[:5],
                )
            )
        return results

    def list_services(self) -> list[ServiceInfo]:
        if not self._services_raw:
            return []

        results: list[ServiceInfo] = []
        for domain, domain_services in self._services_raw.items():
            for svc_name, svc_data in domain_services.items():
                fields: list[ServiceField] = []
                raw_fields = svc_data.get("fields", {})
                for fname, fdata in raw_fields.items():
                    if fname == "advanced_fields" or fname == "fields":
                        continue
                    if not isinstance(fdata, dict):
                        continue
                    fields.append(
                        ServiceField(
                            name=fname,
                            description=fdata.get("description"),
                            required=fdata.get("required", False),
                            example=str(fdata["example"]) if "example" in fdata else None,
                            selector=fdata.get("selector"),
                        )
                    )

                results.append(
                    ServiceInfo(
                        domain=domain,
                        service=svc_name,
                        name=svc_data.get("name"),
                        description=svc_data.get("description"),
                        fields=fields,
                    )
                )

        return sorted(results, key=lambda s: f"{s.domain}.{s.service}")

    def search_services(self, text: str | None = None, domain: str | None = None) -> list[ServiceInfo]:
        all_services = self.list_services()
        if not text and not domain:
            return all_services

        text_lower = text.lower() if text else None
        results: list[ServiceInfo] = []
        for svc in all_services:
            if domain and svc.domain != domain:
                continue
            if text_lower:
                searchable = f"{svc.domain}.{svc.service} {svc.name or ''} {svc.description or ''}".lower()
                if text_lower not in searchable:
                    continue
            results.append(svc)
        return results

    def known_domains(self) -> set[str]:
        domains: set[str] = set()
        for eid in self.all_entity_ids:
            domains.add(self._domain(eid))
        return domains

    def entity_exists(self, entity_id: str) -> bool:
        return entity_id in self._registry or entity_id in self._states

    def extract_and_verify(self, filepath: str, content: str) -> list[EntityReference]:
        """Extract entity references from text and verify each against the registry."""
        domains = self.known_domains()
        domain_alt = "|".join(re.escape(d) for d in sorted(domains, key=len, reverse=True))
        pattern = re.compile(rf"\b({domain_alt})\.[a-z][a-z0-9_]*\b")

        # Build set of known service names to exclude (e.g. light.turn_on)
        service_names: set[str] = set()
        if self._services_raw:
            for svc_domain, svc_actions in self._services_raw.items():
                for svc_name in svc_actions:
                    service_names.add(f"{svc_domain}.{svc_name}")

        seen: set[tuple[str, int]] = set()
        results: list[EntityReference] = []

        for lineno, line in enumerate(content.splitlines(), start=1):
            for match in pattern.finditer(line):
                entity_id = match.group(0)
                if entity_id in service_names:
                    continue
                key = (entity_id, lineno)
                if key in seen:
                    continue
                seen.add(key)

                exists = self.entity_exists(entity_id)
                friendly = self._resolve_friendly_name(entity_id) if exists else None
                results.append(
                    EntityReference(
                        entity_id=entity_id,
                        exists=exists,
                        file=filepath,
                        line=lineno,
                        friendly_name=friendly,
                    )
                )

        return results

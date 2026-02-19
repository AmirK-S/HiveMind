from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.knowledge_item_response_tags_type_0 import KnowledgeItemResponseTagsType0





T = TypeVar("T", bound="KnowledgeItemResponse")



@_attrs_define
class KnowledgeItemResponse:
    """ Response body for GET /knowledge/{item_id} — full content.

        Attributes:
            id (str):
            content (str):
            category (str):
            confidence (float):
            framework (None | str):
            language (None | str):
            version (None | str):
            tags (KnowledgeItemResponseTagsType0 | None):
            org_attribution (str):
            contributed_at (str):
            integrity_verified (bool | None | Unset):
            integrity_warning (None | str | Unset):
     """

    id: str
    content: str
    category: str
    confidence: float
    framework: None | str
    language: None | str
    version: None | str
    tags: KnowledgeItemResponseTagsType0 | None
    org_attribution: str
    contributed_at: str
    integrity_verified: bool | None | Unset = UNSET
    integrity_warning: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        from ..models.knowledge_item_response_tags_type_0 import KnowledgeItemResponseTagsType0
        id = self.id

        content = self.content

        category = self.category

        confidence = self.confidence

        framework: None | str
        framework = self.framework

        language: None | str
        language = self.language

        version: None | str
        version = self.version

        tags: dict[str, Any] | None
        if isinstance(self.tags, KnowledgeItemResponseTagsType0):
            tags = self.tags.to_dict()
        else:
            tags = self.tags

        org_attribution = self.org_attribution

        contributed_at = self.contributed_at

        integrity_verified: bool | None | Unset
        if isinstance(self.integrity_verified, Unset):
            integrity_verified = UNSET
        else:
            integrity_verified = self.integrity_verified

        integrity_warning: None | str | Unset
        if isinstance(self.integrity_warning, Unset):
            integrity_warning = UNSET
        else:
            integrity_warning = self.integrity_warning


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "id": id,
            "content": content,
            "category": category,
            "confidence": confidence,
            "framework": framework,
            "language": language,
            "version": version,
            "tags": tags,
            "org_attribution": org_attribution,
            "contributed_at": contributed_at,
        })
        if integrity_verified is not UNSET:
            field_dict["integrity_verified"] = integrity_verified
        if integrity_warning is not UNSET:
            field_dict["integrity_warning"] = integrity_warning

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.knowledge_item_response_tags_type_0 import KnowledgeItemResponseTagsType0
        d = dict(src_dict)
        id = d.pop("id")

        content = d.pop("content")

        category = d.pop("category")

        confidence = d.pop("confidence")

        def _parse_framework(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        framework = _parse_framework(d.pop("framework"))


        def _parse_language(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        language = _parse_language(d.pop("language"))


        def _parse_version(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        version = _parse_version(d.pop("version"))


        def _parse_tags(data: object) -> KnowledgeItemResponseTagsType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                tags_type_0 = KnowledgeItemResponseTagsType0.from_dict(data)



                return tags_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(KnowledgeItemResponseTagsType0 | None, data)

        tags = _parse_tags(d.pop("tags"))


        org_attribution = d.pop("org_attribution")

        contributed_at = d.pop("contributed_at")

        def _parse_integrity_verified(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        integrity_verified = _parse_integrity_verified(d.pop("integrity_verified", UNSET))


        def _parse_integrity_warning(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        integrity_warning = _parse_integrity_warning(d.pop("integrity_warning", UNSET))


        knowledge_item_response = cls(
            id=id,
            content=content,
            category=category,
            confidence=confidence,
            framework=framework,
            language=language,
            version=version,
            tags=tags,
            org_attribution=org_attribution,
            contributed_at=contributed_at,
            integrity_verified=integrity_verified,
            integrity_warning=integrity_warning,
        )


        knowledge_item_response.additional_properties = d
        return knowledge_item_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset







T = TypeVar("T", bound="KnowledgeSearchResult")



@_attrs_define
class KnowledgeSearchResult:
    """ Single result item in a search response.

        Attributes:
            id (str):
            title (str):
            category (str):
            confidence (float):
            org_attribution (str):
            relevance_score (float):
     """

    id: str
    title: str
    category: str
    confidence: float
    org_attribution: str
    relevance_score: float
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

        category = self.category

        confidence = self.confidence

        org_attribution = self.org_attribution

        relevance_score = self.relevance_score


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "id": id,
            "title": title,
            "category": category,
            "confidence": confidence,
            "org_attribution": org_attribution,
            "relevance_score": relevance_score,
        })

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        category = d.pop("category")

        confidence = d.pop("confidence")

        org_attribution = d.pop("org_attribution")

        relevance_score = d.pop("relevance_score")

        knowledge_search_result = cls(
            id=id,
            title=title,
            category=category,
            confidence=confidence,
            org_attribution=org_attribution,
            relevance_score=relevance_score,
        )


        knowledge_search_result.additional_properties = d
        return knowledge_search_result

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

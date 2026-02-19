from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast

if TYPE_CHECKING:
  from ..models.knowledge_search_result import KnowledgeSearchResult





T = TypeVar("T", bound="KnowledgeSearchResponse")



@_attrs_define
class KnowledgeSearchResponse:
    """ Response body for GET /knowledge/search.

        Attributes:
            results (list[KnowledgeSearchResult]):
            total_found (int):
            next_cursor (None | str):
     """

    results: list[KnowledgeSearchResult]
    total_found: int
    next_cursor: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        from ..models.knowledge_search_result import KnowledgeSearchResult
        results = []
        for results_item_data in self.results:
            results_item = results_item_data.to_dict()
            results.append(results_item)



        total_found = self.total_found

        next_cursor: None | str
        next_cursor = self.next_cursor


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "results": results,
            "total_found": total_found,
            "next_cursor": next_cursor,
        })

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.knowledge_search_result import KnowledgeSearchResult
        d = dict(src_dict)
        results = []
        _results = d.pop("results")
        for results_item_data in (_results):
            results_item = KnowledgeSearchResult.from_dict(results_item_data)



            results.append(results_item)


        total_found = d.pop("total_found")

        def _parse_next_cursor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        next_cursor = _parse_next_cursor(d.pop("next_cursor"))


        knowledge_search_response = cls(
            results=results,
            total_found=total_found,
            next_cursor=next_cursor,
        )


        knowledge_search_response.additional_properties = d
        return knowledge_search_response

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

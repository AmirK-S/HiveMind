from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast






T = TypeVar("T", bound="OutcomeResponse")



@_attrs_define
class OutcomeResponse:
    """ Response body for POST /outcomes.

        Attributes:
            status (str):
            item_id (str):
            outcome (str):
            signal_id (None | str | Unset):
     """

    status: str
    item_id: str
    outcome: str
    signal_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        status = self.status

        item_id = self.item_id

        outcome = self.outcome

        signal_id: None | str | Unset
        if isinstance(self.signal_id, Unset):
            signal_id = UNSET
        else:
            signal_id = self.signal_id


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "status": status,
            "item_id": item_id,
            "outcome": outcome,
        })
        if signal_id is not UNSET:
            field_dict["signal_id"] = signal_id

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = d.pop("status")

        item_id = d.pop("item_id")

        outcome = d.pop("outcome")

        def _parse_signal_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        signal_id = _parse_signal_id(d.pop("signal_id", UNSET))


        outcome_response = cls(
            status=status,
            item_id=item_id,
            outcome=outcome,
            signal_id=signal_id,
        )


        outcome_response.additional_properties = d
        return outcome_response

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

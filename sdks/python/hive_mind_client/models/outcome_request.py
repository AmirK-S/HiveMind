from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.outcome_request_outcome import OutcomeRequestOutcome
from ..types import UNSET, Unset
from typing import cast






T = TypeVar("T", bound="OutcomeRequest")



@_attrs_define
class OutcomeRequest:
    """ Request body for POST /outcomes.

        Attributes:
            item_id (str): UUID of the knowledge item this outcome applies to
            outcome (OutcomeRequestOutcome): Outcome of using this knowledge item
            run_id (None | str | Unset): Optional agent run ID for deduplication and tracing. Strongly recommended —
                prevents double-counting on retries.
     """

    item_id: str
    outcome: OutcomeRequestOutcome
    run_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        item_id = self.item_id

        outcome = self.outcome.value

        run_id: None | str | Unset
        if isinstance(self.run_id, Unset):
            run_id = UNSET
        else:
            run_id = self.run_id


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "item_id": item_id,
            "outcome": outcome,
        })
        if run_id is not UNSET:
            field_dict["run_id"] = run_id

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        item_id = d.pop("item_id")

        outcome = OutcomeRequestOutcome(d.pop("outcome"))




        def _parse_run_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        run_id = _parse_run_id(d.pop("run_id", UNSET))


        outcome_request = cls(
            item_id=item_id,
            outcome=outcome,
            run_id=run_id,
        )


        outcome_request.additional_properties = d
        return outcome_request

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

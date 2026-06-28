"""Tests for the Fusion parts-export ingest contract."""

import json

import pytest

from henley.fusion import DesignPart, load_parts_json


def test_from_dict_maps_fields_and_aliases():
    p = DesignPart.from_dict(
        {"designator": "R1", "mpn": "RC0402", "lcsc": "C25744", "quantity": 3, "value": "10k"}
    )
    assert p.designator == "R1"
    assert p.manufacturer_part == "RC0402"  # 'mpn' alias
    assert p.jlc_code == "C25744"  # 'lcsc' alias
    assert p.quantity == 3
    assert p.value == "10k"


def test_designator_is_required():
    with pytest.raises(ValueError):
        DesignPart.from_dict({"jlcCode": "C1"})


def test_load_parts_json_object_and_list_forms(tmp_path):
    obj = {"parts": [{"designator": "R1", "jlcCode": "C25744"}]}
    f = tmp_path / "parts.json"
    f.write_text(json.dumps(obj))
    parts = load_parts_json(f)
    assert len(parts) == 1 and parts[0].jlc_code == "C25744"

    f.write_text(json.dumps([{"designator": "U1"}]))  # bare-list form
    parts = load_parts_json(f)
    assert parts[0].designator == "U1" and parts[0].quantity == 1

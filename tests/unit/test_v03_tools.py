"""V03 - MCP tools through the Tool Gateway."""

import pytest

from app.mcp.tool_gateway import ToolRejected
from app.models import Principal

ANA = Principal(user_id="ana", role="technician", plants=("PLANT-A",))


def test_tool_discovery_lists_the_three_tools(container):
    assert sorted(container.tools.list_tools(ANA)) == ["get_equipment_info", "get_failure_history", "get_sensor_readings"]


def test_sensor_readings_for_p204_match_the_scenario(container):
    res = container.tools.call(ANA, "get_sensor_readings", {"equipment_id": "P-204"})
    vals = {r.sensor: (r.value, r.unit) for r in res.readings}
    assert vals["bearing_temperature"] == (86.0, "C") and vals["vibration"] == (8.4, "mm/s") and vals["discharge_pressure"] == (2.8, "bar")


def test_typed_results(container):
    info = container.tools.call(ANA, "get_equipment_info", {"equipment_id": "P-204"})
    assert info.type == "pump" and info.plant_id == "PLANT-A"
    hist = container.tools.call(ANA, "get_failure_history", {"equipment_id": "P-204", "limit": 3})
    assert 0 < len(hist.failures) <= 3


@pytest.mark.parametrize("name,args,code", [
    ("delete_everything", {}, "not_allowlisted"),
    ("get_sensor_readings", {}, "invalid_arguments"),
    ("get_sensor_readings", {"equipment_id": 123}, "invalid_arguments"),
    ("get_sensor_readings", {"equipment_id": "P-204", "extra": "x"}, "invalid_arguments"),
    ("get_failure_history", {"equipment_id": "P-204", "limit": 9999}, "invalid_arguments"),
    ("get_sensor_readings", {"equipment_id": "X-999"}, "not_found"),
])
def test_invalid_calls_are_rejected(container, name, args, code):
    with pytest.raises(ToolRejected) as e:
        container.tools.call(ANA, name, args)
    assert e.value.code == code

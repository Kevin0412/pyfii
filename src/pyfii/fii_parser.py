"""XML parser for the project metadata stored in a ``.fii`` file."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


Position = Tuple[float, float]


class FiiParseError(ValueError):
    """Raised when a ``.fii`` document is not valid project XML."""


@dataclass
class FiiFlight:
    """One aircraft declared by an ``ActionFlight`` element."""

    action_name: str
    name: str
    uav_id: Optional[str]
    x: Optional[float]
    y: Optional[float]
    z: Optional[float]


@dataclass
class FiiMetadata:
    device_type: Optional[str]
    field: Optional[int]
    music_name: Optional[str]
    actions: List[str]
    flights: List[FiiFlight]

    @property
    def takeoff_positions(self) -> Dict[str, Position]:
        """Return the XY position for each action group that has one flight."""
        return {
            flight.action_name: (flight.x, flight.y)
            for flight in self.flights
            if flight.x is not None and flight.y is not None
        }


def parse_fii(xml_text: str) -> FiiMetadata:
    """Parse the metadata needed by ``read_fii`` from a ``.fii`` document."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise FiiParseError(f"invalid .fii XML: {error}") from error

    # Collect names first.  The remaining nodes may appear in any XML order.
    actions = _attribute_values(root, "Actions", "actionname")
    flight_names = _attribute_values(root, "ActionFlight", "actionfname")

    uav_ids = _values_by_flight(
        root, "ActionFlightID", "actionfid", flight_names, "UAVID"
    )
    x_values = _values_by_flight(
        root, "ActionFlightPosX", "actionfX", flight_names, "pos"
    )
    y_values = _values_by_flight(
        root, "ActionFlightPosY", "actionfY", flight_names, "pos"
    )
    z_values = _values_by_flight(
        root, "ActionFlightPosZ", "actionfZ", flight_names, "pos"
    )

    flights = []
    used_actions = set()
    for flight_name in flight_names:
        action_name = _longest_prefix(flight_name, actions)
        if action_name is None:
            raise FiiParseError(
                f"ActionFlight {flight_name!r} does not belong to an action group"
            )
        if action_name in used_actions:
            raise FiiParseError(
                f"action group {action_name!r} contains more than one flight"
            )
        used_actions.add(action_name)

        flights.append(
            FiiFlight(
                action_name=action_name,
                name=flight_name,
                uav_id=uav_ids.get(flight_name),
                x=_optional_number(x_values.get(flight_name), "ActionFlightPosX"),
                y=_optional_number(y_values.get(flight_name), "ActionFlightPosY"),
                z=_optional_number(z_values.get(flight_name), "ActionFlightPosZ"),
            )
        )

    area = _first_attribute(root, "AreaL", "AreaL")
    # Preserve read_fii's existing field code: 400 -> 4, 560 -> 5, 600 -> 6.
    field = int(_number(area, "AreaL")) // 100 if area is not None else None
    return FiiMetadata(
        device_type=_first_attribute(root, "DeviceType", "DeviceType"),
        field=field,
        music_name=_first_attribute(root, "MusicName", "path"),
        actions=actions,
        flights=flights,
    )


def _values_by_flight(
    root: ET.Element,
    tag_name: str,
    attribute: str,
    flight_names: List[str],
    separator: str,
) -> Dict[str, str]:
    """Map values such as ``动作组1无人机1pos20`` by their full flight name."""
    result = {}
    for raw_value in _attribute_values(root, tag_name, attribute):
        flight_name = _longest_prefix(raw_value, flight_names, separator)
        if flight_name is None:
            raise FiiParseError(f"{tag_name}: unknown flight in {raw_value!r}")
        if flight_name in result:
            raise FiiParseError(f"{tag_name}: duplicate value for {flight_name!r}")
        prefix = flight_name + separator
        result[flight_name] = raw_value[len(prefix):]
    return result


def _attribute_values(
    root: ET.Element, tag_name: str, attribute: str
) -> List[str]:
    values = []
    for element in root.iter():
        if _tag(element) != tag_name:
            continue
        value = element.attrib.get(attribute)
        if value is None:
            raise FiiParseError(f"{tag_name}: missing {attribute} attribute")
        values.append(value)
    return values


def _longest_prefix(
    value: str, owners: List[str], separator: str = ""
) -> Optional[str]:
    """Use the longest match so 无人机10 is not mistaken for 无人机1."""
    matches = [owner for owner in owners if value.startswith(owner + separator)]
    return max(matches, key=len) if matches else None


def _first_attribute(
    root: ET.Element, tag_name: str, attribute: str
) -> Optional[str]:
    for element in root.iter():
        if _tag(element) == tag_name:
            return element.attrib.get(attribute)
    return None


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _number(value: str, owner: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise FiiParseError(f"{owner}: invalid number {value!r}") from error


def _optional_number(value: Optional[str], owner: str) -> Optional[float]:
    return _number(value, owner) if value is not None else None

"""Tree-based parser for ``webCodeAll.xml``.

This module is intentionally independent from :mod:`pyfii.read`.  It parses
Blockly XML into the same ``dots`` event format used by the existing trajectory
code.  :mod:`pyfii.read` uses it by default and retains the legacy parser as a
fallback for malformed or unsupported documents.
"""

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple
import xml.etree.ElementTree as ET


Dot = List[object]
Point = Tuple[float, float, float]


class XmlParseError(ValueError):
    """Raised when a supported block contains invalid or incomplete data."""


@dataclass
class XmlParseResult:
    """Result of compiling one ``webCodeAll.xml`` document."""

    dots: List[Dot]
    warnings: List[str]
    time_ms: float
    end_ms: float
    points: Dict[str, Point]
    ignored_blocks: List[str]

    def as_legacy_tuple(self) -> Tuple[List[Dot], List[str], float, float]:
        """Return the four values produced by the legacy ``read_xml``."""

        return self.dots, self.warnings, self.time_ms, self.end_ms


@dataclass
class _State:
    time_ms: float = 0
    x: float = 0
    y: float = 0
    velocity: float = 0
    acceleration: float = 0
    angular_velocity: float = 0


def parse_web_code(
    xml_text: str,
    start_position: Optional[Sequence[float]] = None,
    points: Optional[Mapping[str, Sequence[float]]] = None,
) -> XmlParseResult:
    """Compile ``webCodeAll.xml`` text into time-ordered ``dots`` events.

    ``start_position`` is the takeoff position read from the project ``.fii``
    file.  It is required when the XML contains a ``Goertek_Start`` block.
    ``points`` can provide named points collected from other drone files in the
    same project.
    """

    root = _parse_root(xml_text)
    point_map = _copy_points(points)
    point_map.update(_collect_points(root))

    parser = _WebCodeParser(start_position=start_position, points=point_map)
    return parser.parse(root)


def collect_points(xml_text: str) -> Dict[str, Point]:
    """Return all named ``Goertek_Point`` definitions in one document."""

    return _collect_points(_parse_root(xml_text))


class _WebCodeParser:
    def __init__(
        self,
        start_position: Optional[Sequence[float]],
        points: Dict[str, Point],
    ) -> None:
        if start_position is not None and len(start_position) != 2:
            raise ValueError("start_position must contain x and y")

        self.start_position = start_position
        self.points = points
        self.state = _State()
        self.dots: List[Dot] = []
        self.warnings: List[str] = []
        self.end_ms: float = 0
        self.ignored_blocks: Set[str] = set()

    def parse(self, root: ET.Element) -> XmlParseResult:
        top_blocks = (
            [root]
            if _tag_name(root) == "block"
            else _direct_children(root, "block")
        )
        start_blocks = [
            block
            for block in top_blocks
            if block.attrib.get("type", "").startswith("Goertek_Start")
        ]
        if len(start_blocks) != 1:
            raise XmlParseError(
                "webCodeAll.xml must contain exactly one top-level Goertek_Start"
            )

        loose_blocks = [block for block in top_blocks if block is not start_blocks[0]]
        if loose_blocks:
            block_count = sum(_count_blocks(block) for block in loose_blocks)
            self.warnings.append(
                f"Ignored {len(loose_blocks)} disconnected Blockly group(s) "
                f"containing {block_count} block(s). "
                f"检测到{len(loose_blocks)}组未拼接积木（共{block_count}个），已忽略。"
            )

        # Only the chain connected to Goertek_Start is executable.
        self._run_chain(start_blocks[0])

        return XmlParseResult(
            dots=self.dots,
            warnings=self.warnings,
            time_ms=self.state.time_ms,
            end_ms=self.end_ms,
            points=dict(self.points),
            ignored_blocks=sorted(self.ignored_blocks),
        )

    def _run_chain(self, block: ET.Element) -> None:
        """Run one block, its statements, and then its ``next`` block."""

        current = block
        while current is not None:
            block_type = _required_attribute(current, "type", "block")

            if block_type == "controls_repeat":
                self._run_repeat(current)
            else:
                self._run_block(current, block_type)
                for statement in _direct_children(current, "statement"):
                    child = _first_child(statement, "block")
                    if child is not None:
                        self._run_chain(child)

            next_element = _first_child(current, "next")
            current = (
                _first_child(next_element, "block")
                if next_element is not None
                else None
            )

    def _run_repeat(self, block: ET.Element) -> None:
        fields = _fields(block)
        count_text = _required_field(fields, "TIMES", "controls_repeat")
        try:
            count = int(count_text)
        except ValueError as error:
            raise XmlParseError(
                f"controls_repeat: invalid TIMES value {count_text!r}"
            ) from error
        if count < 0:
            raise XmlParseError("controls_repeat: TIMES must not be negative")

        bodies = []
        for statement in _direct_children(block, "statement"):
            body = _first_child(statement, "block")
            if body is not None:
                bodies.append(body)

        for _ in range(count):
            for body in bodies:
                self._run_chain(body)

    def _run_block(self, block: ET.Element, block_type: str) -> None:
        fields = _fields(block)

        if block_type.startswith("block_inittime"):
            new_time = _time_to_ms(
                _required_field(fields, "time", block_type), block_type
            )
            if new_time < self.state.time_ms:
                raise XmlParseError(
                    f"{block_type}: time moves backwards from "
                    f"{self.state.time_ms:g} to {new_time:g} ms"
                )
            self.state.time_ms = new_time

        elif block_type.startswith("block_delay"):
            self.state.time_ms += _number_field(fields, "time", block_type)

        elif block_type.startswith("Goertek_Start"):
            if self.start_position is None:
                raise XmlParseError(
                    "Goertek_Start: takeoff position must come from the .fii file"
                )
            self.state.x = float(self.start_position[0])
            self.state.y = float(self.start_position[1])
            self._emit(
                [
                    self.state.time_ms,
                    self.state.x,
                    self.state.y,
                    0,
                    200,
                    400,
                    "move2",
                ]
            )

        elif block_type.startswith("Goertek_TakeOff"):
            altitude = _number_field(fields, "alt", block_type)
            self._emit(
                [
                    self.state.time_ms,
                    self.state.x,
                    self.state.y,
                    altitude,
                    200,
                    400,
                    "move2",
                ]
            )

        elif block_type.startswith("Goertek_Land"):
            self._emit([self.state.time_ms, "land"])

        elif block_type.startswith("Goertek_HorizontalSpeed"):
            self.state.velocity = _number_field(fields, "VH", block_type)
            self.state.acceleration = _number_field(fields, "AH", block_type)

        elif block_type.startswith("Goertek_MoveToCoord"):
            self._ensure_motion_defaults()
            self._emit(
                [
                    self.state.time_ms,
                    _number_field(fields, "X", block_type),
                    _number_field(fields, "Y", block_type),
                    _number_field(fields, "Z", block_type),
                    self.state.velocity,
                    self.state.acceleration,
                    "move2",
                ]
            )

        elif block_type.startswith("Goertek_MoveToPoint"):
            self._ensure_motion_defaults()
            name = _required_field(fields, "point", block_type)
            try:
                x, y, z = self.points[name]
            except KeyError as error:
                raise XmlParseError(
                    f"{block_type}: unknown point {name!r}"
                ) from error
            self._emit(
                [
                    self.state.time_ms,
                    x,
                    y,
                    z,
                    self.state.velocity,
                    self.state.acceleration,
                    "move2",
                ]
            )

        elif block_type.startswith("Goertek_Point"):
            # Point definitions were collected before execution so forward
            # references and project-wide point maps both work.
            return

        elif block_type.startswith("Goertek_Move"):
            self._ensure_motion_defaults()
            self._emit(
                [
                    self.state.time_ms,
                    _number_field(fields, "X", block_type),
                    _number_field(fields, "Y", block_type),
                    _number_field(fields, "Z", block_type),
                    self.state.velocity,
                    self.state.acceleration,
                    "move",
                ]
            )

        elif block_type.startswith("Goertek_AngularVelocity"):
            self.state.angular_velocity = _number_field(fields, "w", block_type)

        elif block_type.startswith("Goertek_TurnTo"):
            self._emit_turn(fields, block_type, "turn2")

        elif block_type.startswith("Goertek_Turn"):
            self._emit_turn(fields, block_type, "turn")

        elif "Goertek_LEDTurnOnAllSingleColor" in block_type:
            color = _color_to_bgr(
                _required_field(fields, "color1", block_type), block_type
            )
            self._emit([self.state.time_ms, color, "TurnOnAllSingleColor"])

        elif "Goertek_LEDTurnOffAll" in block_type:
            self._emit([self.state.time_ms, "TurnOffAll"])

        else:
            self.ignored_blocks.add(block_type)

    def _ensure_motion_defaults(self) -> None:
        if self.state.velocity == 0:
            self.state.velocity = 60
            self.warnings.append(
                "Velcity is not defined.Default 60cm/s.速度未定义。默认60cm/s。"
            )
        if self.state.acceleration == 0:
            self.state.acceleration = 100
            self.warnings.append(
                "Acceleration is not defined.Default 100cm/s^2."
                "加速度未定义。默认100cm/s^2。"
            )

    def _emit_turn(
        self, fields: Mapping[str, str], block_type: str, event_type: str
    ) -> None:
        if self.state.angular_velocity == 0:
            self.state.angular_velocity = 60
            self.warnings.append(
                "Arate is not defined.Default 60°/s.角速度未定义。默认60°/s。"
            )

        direction = _required_field(fields, "turnDirection", block_type)
        angle = _number_field(fields, "angle", block_type)
        if direction == "r":
            angle = -angle
        elif direction != "l":
            raise XmlParseError(
                f"{block_type}: invalid turnDirection {direction!r}"
            )
        self._emit(
            [self.state.time_ms, angle, self.state.angular_velocity, event_type]
        )

    def _emit(self, dot: Dot) -> None:
        self.dots.append(dot)
        self.end_ms = max(self.end_ms, self.state.time_ms)


def _parse_root(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise XmlParseError(f"invalid XML: {error}") from error


def _collect_points(root: ET.Element) -> Dict[str, Point]:
    points: Dict[str, Point] = {}
    for element in root.iter():
        if _tag_name(element) != "block":
            continue
        block_type = element.attrib.get("type", "")
        if not block_type.startswith("Goertek_Point"):
            continue
        fields = _fields(element)
        name = _required_field(fields, "name", block_type)
        points[name] = (
            _number_field(fields, "X", block_type),
            _number_field(fields, "Y", block_type),
            _number_field(fields, "Z", block_type),
        )
    return points


def _copy_points(
    points: Optional[Mapping[str, Sequence[float]]],
) -> Dict[str, Point]:
    if points is None:
        return {}
    copied = {}
    for name, point in points.items():
        if len(point) != 3:
            raise ValueError(f"point {name!r} must contain x, y and z")
        copied[name] = (float(point[0]), float(point[1]), float(point[2]))
    return copied


def _tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _count_blocks(element: ET.Element) -> int:
    return sum(_tag_name(child) == "block" for child in element.iter())


def _direct_children(element: ET.Element, name: str) -> List[ET.Element]:
    return [child for child in element if _tag_name(child) == name]


def _first_child(element: ET.Element, name: str) -> Optional[ET.Element]:
    for child in element:
        if _tag_name(child) == name:
            return child
    return None


def _fields(block: ET.Element) -> Dict[str, str]:
    fields = {}
    for field in _direct_children(block, "field"):
        name = field.attrib.get("name")
        if name is not None:
            fields[name] = (field.text or "").strip()
    return fields


def _required_field(
    fields: Mapping[str, str], name: str, block_type: str
) -> str:
    try:
        return fields[name]
    except KeyError as error:
        raise XmlParseError(f"{block_type}: missing field {name!r}") from error


def _number_field(fields: Mapping[str, str], name: str, block_type: str) -> float:
    value = _required_field(fields, name, block_type)
    return _to_float(value, f"{block_type}.{name}")


def _required_attribute(element: ET.Element, name: str, owner: str) -> str:
    try:
        return element.attrib[name]
    except KeyError as error:
        raise XmlParseError(f"{owner}: missing attribute {name!r}") from error


def _to_float(value: str, owner: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise XmlParseError(f"{owner}: invalid number {value!r}") from error


def _time_to_ms(value: str, block_type: str) -> float:
    parts = value.split(":")
    if len(parts) != 2:
        raise XmlParseError(f"{block_type}.time: expected MM:SS, got {value!r}")
    minutes = _to_float(parts[0], f"{block_type}.time")
    seconds = _to_float(parts[1], f"{block_type}.time")
    return (minutes * 60 + seconds) * 1000


def _color_to_bgr(value: str, block_type: str) -> Tuple[int, int, int]:
    if len(value) != 7 or not value.startswith("#"):
        raise XmlParseError(
            f"{block_type}.color1: expected #RRGGBB, got {value!r}"
        )
    try:
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
    except ValueError as error:
        raise XmlParseError(
            f"{block_type}.color1: invalid color {value!r}"
        ) from error
    return blue, green, red

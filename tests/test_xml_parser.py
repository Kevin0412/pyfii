import unittest

from pyfii.read import read_xml, read_xml_points
from pyfii.xml_parser import XmlParseError, collect_points, parse_web_code


class XmlParserTests(unittest.TestCase):
    def test_parses_fields_by_name_instead_of_line_position(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block y="999" type="Goertek_Start" x="999">
            <next>
              <block type="Goertek_HorizontalSpeed">
                <field name="AH">100</field>
                <field name="VH">60</field>
                <next>
                  <block type="Goertek_MoveToCoord2">
                    <field name="Z">120</field>
                    <field name="X">30</field>
                    <field name="Y">40</field>
                    <next>
                      <block type="Goertek_LEDTurnOnAllSingleColor2">
                        <field name="color1">#ff8000</field>
                      </block>
                    </next>
                  </block>
                </next>
              </block>
            </next>
          </block>
        </xml>
        """

        result = parse_web_code(xml, start_position=(10, 20))

        self.assertEqual(
            result.dots,
            [
                [0, 10.0, 20.0, 0, 200, 400, "move2"],
                [0, 30.0, 40.0, 120.0, 60.0, 100.0, "move2"],
                [0, (0, 128, 255), "TurnOnAllSingleColor"],
            ],
        )
        self.assertEqual(result.warnings, [])

    def test_expands_repeat_statement_in_execution_order(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Start" x="10" y="20">
            <next>
              <block type="controls_repeat">
                <field name="TIMES">2</field>
                <statement name="DO">
                  <block type="Goertek_LEDTurnOnAllSingleColor2">
                    <field name="color1">#ff0000</field>
                    <next>
                      <block type="block_delay">
                        <field name="delay">0</field>
                        <field name="time">100</field>
                        <next>
                          <block type="Goertek_LEDTurnOffAll2" />
                        </next>
                      </block>
                    </next>
                  </block>
                </statement>
                <next>
                  <block type="Goertek_Land" />
                </next>
              </block>
            </next>
          </block>
        </xml>
        """

        result = parse_web_code(xml, start_position=(10, 20))

        self.assertEqual(
            result.dots,
            [
                [0, 10.0, 20.0, 0, 200, 400, "move2"],
                [0, (0, 0, 255), "TurnOnAllSingleColor"],
                [100.0, "TurnOffAll"],
                [100.0, (0, 0, 255), "TurnOnAllSingleColor"],
                [200.0, "TurnOffAll"],
                [200.0, "land"],
            ],
        )
        self.assertEqual(result.time_ms, 200.0)
        self.assertEqual(result.end_ms, 200.0)

    def test_collects_points_before_executing_forward_reference(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Start" x="0" y="0">
            <next>
              <block type="Goertek_MoveToPoint">
                <field name="point">target</field>
                <next>
                  <block type="Goertek_Point">
                    <field name="name">target</field>
                    <field name="X">100</field>
                    <field name="Y">200</field>
                    <field name="Z">150</field>
                  </block>
                </next>
              </block>
            </next>
          </block>
        </xml>
        """

        self.assertEqual(collect_points(xml), {"target": (100.0, 200.0, 150.0)})

        result = parse_web_code(xml, start_position=(0, 0))
        self.assertEqual(
            result.dots[1], [0, 100.0, 200.0, 150.0, 60, 100, "move2"]
        )
        self.assertEqual(len(result.warnings), 2)

    def test_tracks_absolute_time_takeoff_and_turn_state(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Start" x="10" y="20">
            <next>
              <block type="block_inittime">
                <field name="time">00:05</field>
                <statement name="functionIntit">
                  <block type="Goertek_TakeOff2">
                    <field name="alt">100</field>
                    <next>
                      <block type="Goertek_AngularVelocity">
                        <field name="w">30</field>
                        <next>
                          <block type="Goertek_TurnTo">
                            <field name="turnDirection">l</field>
                            <field name="angle">90</field>
                            <next>
                              <block type="block_delay">
                                <field name="time">250</field>
                                <next>
                                  <block type="Goertek_Turn">
                                    <field name="turnDirection">r</field>
                                    <field name="angle">45</field>
                                  </block>
                                </next>
                              </block>
                            </next>
                          </block>
                        </next>
                      </block>
                    </next>
                  </block>
                </statement>
              </block>
            </next>
          </block>
        </xml>
        """

        result = parse_web_code(xml, start_position=(100, 200))

        self.assertEqual(
            result.dots,
            [
                [0, 100.0, 200.0, 0, 200, 400, "move2"],
                [5000.0, 100.0, 200.0, 100.0, 200, 400, "move2"],
                [5000.0, 90.0, 30.0, "turn2"],
                [5250.0, -45.0, 30.0, "turn"],
            ],
        )
        self.assertEqual(result.time_ms, 5250.0)
        self.assertEqual(result.warnings, [])

    def test_start_requires_takeoff_position_from_fii(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Start" x="10" y="20" />
        </xml>
        """

        with self.assertRaisesRegex(XmlParseError, "must come from the .fii"):
            parse_web_code(xml)

    def test_read_xml_uses_tree_parser_as_the_main_route(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Start" x="999" y="999">
            <next>
              <block type="Goertek_HorizontalSpeed">
                <field name="AH">100</field>
                <field name="VH">60</field>
                <next>
                  <block type="Goertek_MoveToCoord2">
                    <field name="Z">120</field>
                    <field name="X">30</field>
                    <field name="Y">40</field>
                  </block>
                </next>
              </block>
            </next>
          </block>
        </xml>
        """

        dots, warnings, _, _ = read_xml(xml, fii=[10, 20], points={})

        self.assertEqual(dots[0], [0, 10.0, 20.0, 0, 200, 400, "move2"])
        self.assertEqual(dots[1], [0, 30.0, 40.0, 120.0, 60.0, 100.0, "move2"])
        self.assertEqual(warnings, [])

    def test_read_xml_points_uses_named_fields(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Point">
            <field name="Z">150</field>
            <field name="name">target</field>
            <field name="Y">200</field>
            <field name="X">100</field>
          </block>
        </xml>
        """

        self.assertEqual(read_xml_points(xml), {"target": (100.0, 200.0, 150.0)})

    def test_read_xml_falls_back_for_malformed_legacy_xml(self):
        xml = """<xml xmlns="http://www.w3.org/1999/xhtml">
  <block type="Goertek_Start" x="999" y="999">"""

        with self.assertWarnsRegex(RuntimeWarning, "using the legacy parser"):
            dots, _, _, _ = read_xml(xml, fii=[10, 20], points={})

        self.assertEqual(dots, [[0, 10, 20, 0, 200, 400, "move2"]])

    def test_ignores_unconnected_top_level_blocks(self):
        xml = """
        <xml xmlns="http://www.w3.org/1999/xhtml">
          <block type="Goertek_Start" x="0" y="0">
            <next>
              <block type="block_inittime">
                <field name="time">01:05</field>
                <statement name="functionIntit">
                  <block type="Goertek_Land" />
                </statement>
              </block>
            </next>
          </block>
          <block type="block_inittime" x="0" y="4528">
            <field name="time">00:00</field>
          </block>
          <block type="Goertek_MoveToCoord2" x="0" y="4614">
            <field name="X">999</field>
            <field name="Y">999</field>
            <field name="Z">999</field>
          </block>
        </xml>
        """

        result = parse_web_code(xml, start_position=(10, 20))

        self.assertEqual(
            result.dots,
            [
                [0, 10.0, 20.0, 0, 200, 400, "move2"],
                [65000.0, "land"],
            ],
        )
        self.assertEqual(result.time_ms, 65000.0)

    def test_reports_ignored_blocks_and_rejects_bad_supported_blocks(self):
        ignored = parse_web_code(
            """
            <xml xmlns="http://www.w3.org/1999/xhtml">
              <block type="Goertek_Start" x="0" y="0">
                <next>
                  <block type="Goertek_UnLock" />
                </next>
              </block>
            </xml>
            """,
            start_position=(0, 0),
        )
        self.assertEqual(ignored.ignored_blocks, ["Goertek_UnLock"])

        with self.assertRaisesRegex(XmlParseError, "missing field 'Z'"):
            parse_web_code(
                """
                <xml xmlns="http://www.w3.org/1999/xhtml">
                  <block type="Goertek_Start" x="0" y="0">
                    <next>
                      <block type="Goertek_MoveToCoord">
                        <field name="X">1</field>
                        <field name="Y">2</field>
                      </block>
                    </next>
                  </block>
                </xml>
                """,
                start_position=(0, 0),
            )


if __name__ == "__main__":
    unittest.main()

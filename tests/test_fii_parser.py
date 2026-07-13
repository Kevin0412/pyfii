import unittest
from unittest.mock import patch

from pyfii.fii_parser import FiiParseError, parse_fii
from pyfii.read import _read_fii_metadata


class FiiParserTests(unittest.TestCase):
    def test_parses_project_metadata_and_takeoff_positions(self):
        xml = """
        <GoertekGraphicXml>
          <ActionFlightPosY actionfY="动作组10无人机10pos220" />
          <AreaL AreaL="560" />
          <ActionFlightID actionfid="动作组1无人机1UAVID10001" />
          <Actions actionname="动作组1" />
          <DeviceType DeviceType="F600" />
          <ActionFlight actionfname="动作组10无人机10" />
          <ActionFlightPosZ actionfZ="动作组1无人机1pos0" />
          <MusicName path="music" />
          <ActionFlightPosX actionfX="动作组1无人机1pos10" />
          <Actions actionname="动作组10" />
          <ActionFlightID actionfid="动作组10无人机10UAVID10010" />
          <ActionFlightPosY actionfY="动作组1无人机1pos20" />
          <ActionFlight actionfname="动作组1无人机1" />
          <ActionFlightPosX actionfX="动作组10无人机10pos110" />
          <ActionFlightPosZ actionfZ="动作组10无人机10pos5" />
        </GoertekGraphicXml>
        """

        metadata = parse_fii(xml)

        self.assertEqual(metadata.device_type, "F600")
        self.assertEqual(metadata.field, 5)
        self.assertEqual(metadata.music_name, "music")
        self.assertEqual(metadata.actions, ["动作组1", "动作组10"])
        self.assertEqual(metadata.flights[0].name, "动作组10无人机10")
        self.assertEqual(metadata.flights[0].action_name, "动作组10")
        self.assertEqual(metadata.flights[0].uav_id, "10010")
        self.assertEqual(
            (metadata.flights[0].x, metadata.flights[0].y, metadata.flights[0].z),
            (110.0, 220.0, 5.0),
        )
        self.assertEqual(
            metadata.takeoff_positions,
            {"动作组1": (10.0, 20.0), "动作组10": (110.0, 220.0)},
        )

    def test_optional_project_metadata_can_be_absent(self):
        metadata = parse_fii("<GoertekGraphicXml />")

        self.assertIsNone(metadata.device_type)
        self.assertIsNone(metadata.field)
        self.assertIsNone(metadata.music_name)
        self.assertEqual(metadata.actions, [])
        self.assertEqual(metadata.flights, [])
        self.assertEqual(metadata.takeoff_positions, {})

    def test_rejects_malformed_fii_xml(self):
        with self.assertRaisesRegex(FiiParseError, "invalid .fii XML"):
            parse_fii("<GoertekGraphicXml>")

    def test_read_fii_metadata_falls_back_to_legacy_reader(self):
        legacy_result = ("F400", 4, None, ["动作组1"], {"动作组1": (10, 20)})

        with patch(
            "pyfii.read._read_fii_metadata_legacy", return_value=legacy_result
        ) as fallback:
            with self.assertWarnsRegex(RuntimeWarning, "using the legacy parser"):
                result = _read_fii_metadata("<GoertekGraphicXml>")

        self.assertEqual(result, legacy_result)
        fallback.assert_called_once()


if __name__ == "__main__":
    unittest.main()

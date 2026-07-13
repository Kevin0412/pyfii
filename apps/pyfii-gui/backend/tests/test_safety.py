import unittest

from pyfii_gui_api.services.safety import analyze_safety


class SafetyAnalysisTests(unittest.TestCase):
    def analyze(self, warning_messages):
        return analyze_safety(
            data=[],
            warnings=warning_messages,
            source_fps=60,
            field=6,
            device="F400",
        )

    def test_preserves_unclassified_core_warning_as_visible_event(self):
        warning = (
            "d3 无人机3:Ignored 5 disconnected Blockly group(s) "
            "containing 30 block(s). 检测到5组未拼接积木（共30个），已忽略。"
        )

        result = self.analyze([warning])

        self.assertEqual(result["summary"]["level"], "warning")
        self.assertEqual(result["summary"]["category_counts"]["core_warning"], 1)
        self.assertEqual(result["events"][0]["category"], "core_warning")
        self.assertEqual(result["events"][0]["type"], "core_warning")
        self.assertEqual(result["events"][0]["drone_a"], 3)
        self.assertEqual(result["events"][0]["message"], warning)

    def test_keeps_distance_error_separate_from_generic_warning(self):
        distance = (
            "In 2s,distance between d1 and d2 is less than 17cm."
            "在2秒，无人机1和无人机2之间的距离小于17厘米。"
        )

        result = self.analyze([distance, "Acceleration is not defined."])

        self.assertEqual(result["summary"]["level"], "error")
        self.assertEqual(result["summary"]["error_count"], 1)
        self.assertEqual(result["summary"]["warning_count"], 1)
        self.assertEqual(
            [event["category"] for event in result["events"]],
            ["distance_17", "core_warning"],
        )

    def test_deduplicates_identical_generic_warnings(self):
        result = self.analyze(["same warning", "same warning"])

        self.assertEqual(len(result["events"]), 1)


if __name__ == "__main__":
    unittest.main()

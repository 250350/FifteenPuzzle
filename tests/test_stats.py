import json
import time
import unittest

from fifteen.stats import SearchStats, Timer


class StatsTest(unittest.TestCase):
    def test_set_solution(self):
        s = SearchStats()
        s.set_solution("LUR")
        self.assertEqual((s.result, s.solution_length, s.solution), ("solved", 3, "LUR"))
        s.set_solution(None)
        self.assertEqual((s.result, s.solution_length, s.solution), ("not_found", -1, ""))

    def test_peak_and_json_rounding(self):
        s = SearchStats(time_ms=1.23456789)
        s.update_peak(5)
        s.update_peak(3)
        self.assertEqual(s.peak_stored_states, 5)
        self.assertEqual(json.loads(s.to_json())["time_ms"], 1.235)

    def test_timer(self):
        with Timer() as t:
            time.sleep(0.01)
        self.assertGreater(t.elapsed_ms, 5)


if __name__ == "__main__":
    unittest.main()

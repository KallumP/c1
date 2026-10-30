"""
tests for tools/generate_level_terrain.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import generate_level_terrain  # noqa: E402
import nslevel  # noqa: E402


class Args(unittest.TestCase):
    def test_a_map_alone_uses_the_default_scale_and_no_turn(self):
        self.assertEqual(("maps/x", None, nslevel.MAP_SCALE, 0), generate_level_terrain.parse_args(["maps/x"]))

    def test_name_and_options_in_any_order(self):
        self.assertEqual(("maps/x", "y", 256, 90),
                         generate_level_terrain.parse_args(["--turn", "90", "maps/x", "--scale", "256", "y"]))

    def test_no_map_is_an_error(self):
        with self.assertRaises(ValueError):
            generate_level_terrain.parse_args([])
        with self.assertRaises(ValueError):
            generate_level_terrain.parse_args(["maps/x", "--turn"])

    def test_without_a_map_it_prints_usage(self):
        self.assertEqual(1, generate_level_terrain.main([]))


if __name__ == "__main__":
    unittest.main()

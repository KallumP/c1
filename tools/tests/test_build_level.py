"""
tests for tools/build_level.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import sys
import tempfile
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import build_level  # noqa: E402
import nslevel  # noqa: E402


def source_folder(cfg=None):
    """a temporary level source folder, holding level.cfg with the text cfg (if given)"""
    folder = tempfile.mkdtemp()
    if cfg is not None:
        with open(os.path.join(folder, "level.cfg"), "w") as f:
            f.write(cfg)
    return folder


class Args(unittest.TestCase):
    def test_a_source_alone_leaves_scale_and_turn_to_it(self):
        self.assertEqual(("level_src/x", None, None, None), build_level.parse_args(["level_src/x"]))

    def test_name_and_options_in_any_order(self):
        self.assertEqual(("level_src/x", "y", 256, 90),
                         build_level.parse_args(["--turn", "90", "level_src/x", "--scale", "256", "y"]))

    def test_no_source_is_an_error(self):
        with self.assertRaises(ValueError):
            build_level.parse_args([])
        with self.assertRaises(ValueError):
            build_level.parse_args(["level_src/x", "--turn"])

    def test_too_big_says_the_largest_scale_that_fits(self):
        # 20000 long at scale 1000 with a 256 margin that doesn't scale:
        # (16384 - 256) / (20000 - 256) of 1000, rounded down to a 10
        e = build_level.blendmap.TooBig(2, 20000, 16384, fixed=256)
        self.assertEqual(810, build_level.fitting_scale(1000, e))

    def test_levels_are_built_into_build_levels(self):
        self.assertEqual(os.path.normpath(os.path.join(TOOLS, "..", "build", "levels")),
                         os.path.normpath(nslevel.LEVELS_DIR))

    def test_without_a_source_it_prints_usage(self):
        self.assertEqual(1, build_level.main([]))


class LevelCfg(unittest.TestCase):
    def test_without_a_level_cfg_it_uses_the_default_scale_and_no_turn(self):
        self.assertEqual((nslevel.MAP_SCALE, 0), build_level.level_options(source_folder(), None, None))

    def test_level_cfg_sets_scale_and_turn(self):
        folder = source_folder("# the castle\n\nturn = 270\nscale=2000\n")
        self.assertEqual((2000, 270), build_level.level_options(folder, None, None))

    def test_level_cfg_can_set_just_one(self):
        self.assertEqual((nslevel.MAP_SCALE, 90), build_level.level_options(source_folder("turn = 90\n"), None, None))

    def test_the_command_line_overrides_level_cfg(self):
        folder = source_folder("turn = 270\nscale = 2000\n")
        self.assertEqual((1000, 270), build_level.level_options(folder, 1000, None))
        self.assertEqual((2000, 0), build_level.level_options(folder, None, 0))

    def assert_cfg_error(self, cfg, *says):
        """level.cfg holding cfg is a ValueError naming the file, and saying
        each of says"""
        with self.assertRaises(ValueError) as e:
            build_level.read_level_cfg(source_folder(cfg))
        for said in ("level.cfg",) + says:
            self.assertIn(said, str(e.exception))

    def test_a_value_that_isnt_a_number_is_an_error(self):
        self.assert_cfg_error("turn = 90\nscale = big\n", "line 2", "scale", "big")

    def test_an_unknown_key_is_an_error(self):
        self.assert_cfg_error("tilt = 90\n", "line 1", "tilt")

    def test_a_line_without_a_value_is_an_error(self):
        self.assert_cfg_error("scale\n", "line 1")

    def test_a_bad_level_cfg_stops_with_a_message(self):
        folder = source_folder("scale = big\n")
        with open(os.path.join(folder, "x.obj"), "w") as f:
            f.write("")
        self.assertEqual(1, build_level.main([folder]))


if __name__ == "__main__":
    unittest.main()

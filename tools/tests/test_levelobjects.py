"""
tests for tools/levelobjects.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import levelobjects  # noqa: E402


class ReadObjects(unittest.TestCase):
    def test_each_object_has_a_kind_and_a_position(self):
        objects = levelobjects.read_objects('[{"kind": "spawn", "at": [0, 2, 0.5]},'
                                            ' {"kind": "end", "at": [1, 40, 3]}]')
        self.assertEqual([("spawn", (0, 2, 0.5)), ("end", (1, 40, 3))], [(o.kind, o.at) for o in objects])

    def test_no_objects_is_fine(self):
        self.assertEqual([], levelobjects.read_objects("[]"))

    def assert_error(self, text, *says):
        """text is a ValueError saying each of says"""
        with self.assertRaises(ValueError) as e:
            levelobjects.read_objects(text)
        for said in says:
            self.assertIn(said, str(e.exception))

    def test_it_has_to_be_json(self):
        self.assert_error('[{"kind": "spawn"', "JSON")

    def test_it_has_to_be_a_list_of_objects(self):
        self.assert_error('{"kind": "spawn", "at": [0, 0, 0]}', "list")
        self.assert_error('["spawn"]', "object 1")

    def test_an_unknown_kind_is_an_error(self):
        self.assert_error('[{"kind": "spawn", "at": [0, 0, 0]}, {"kind": "crate", "at": [0, 0, 0]}]',
                          "object 2", "crate", "spawn", "end")

    def test_a_missing_kind_is_an_error(self):
        self.assert_error('[{"at": [0, 0, 0]}]', "object 1", "kind")

    def test_at_has_to_be_three_numbers(self):
        self.assert_error('[{"kind": "end"}]', "object 1", "at")
        self.assert_error('[{"kind": "end", "at": [0, 0]}]', "object 1", "at")
        self.assert_error('[{"kind": "end", "at": [0, "up", 0]}]', "object 1", "at")
        self.assert_error('[{"kind": "end", "at": [0, true, 0]}]', "object 1", "at")

    def test_an_unknown_setting_is_an_error(self):
        self.assert_error('[{"kind": "end", "at": [0, 0, 0], "spin": 1}]', "object 1", "spin")

    def test_only_one_spawn_and_one_end(self):
        self.assert_error('[{"kind": "spawn", "at": [0, 0, 0]}, {"kind": "spawn", "at": [0, 1, 0]}]',
                          "object 2", "spawn")
        self.assert_error('[{"kind": "end", "at": [0, 0, 0]}, {"kind": "end", "at": [0, 1, 0]}]',
                          "object 2", "end")


if __name__ == "__main__":
    unittest.main()

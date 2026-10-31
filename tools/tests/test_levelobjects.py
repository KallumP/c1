"""
tests for tools/levelobjects.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import blendmap  # noqa: E402
import levelobjects  # noqa: E402


class ReadObjects(unittest.TestCase):
    def test_each_object_has_a_kind_and_a_position(self):
        objects = levelobjects.read_objects('[{"kind": "spawn", "at": [0, 2, 0.5]},'
                                            ' {"kind": "end", "at": [1, 40, 3]}]')
        self.assertEqual([("spawn", (0, 2, 0.5)), ("end", (1, 40, 3))], [(o.kind, o.at) for o in objects])

    def test_raise_lifts_an_object_off_the_ground_it_goes_on(self):
        [end] = levelobjects.read_objects('[{"kind": "end", "at": [0, 40, 1], "raise": 0.25}]')
        self.assertEqual(0.25, end.raise_by)

    def test_raise_is_0_by_default(self):
        [end] = levelobjects.read_objects('[{"kind": "end", "at": [0, 40, 1]}]')
        self.assertEqual(0, end.raise_by)

    def test_raise_has_to_be_a_number(self):
        self.assert_error('[{"kind": "end", "at": [0, 0, 0], "raise": "up"}]', "object 1", "raise")

    def test_a_box_has_a_subtype_and_stacks_one_high_by_default(self):
        [box] = levelobjects.read_objects('[{"kind": "box", "subtype": 2, "at": [0, 5, 0]}]')
        self.assertEqual(("box", (0, 5, 0), 2, 1), (box.kind, box.at, box.subtype, box.stack))

    def test_a_box_can_be_a_stack(self):
        [box] = levelobjects.read_objects('[{"kind": "box", "subtype": 2, "at": [0, 5, 0], "stack": 3}]')
        self.assertEqual(3, box.stack)

    def test_a_level_can_have_many_boxes(self):
        objects = levelobjects.read_objects('[{"kind": "box", "subtype": 2, "at": [0, 5, 0]},'
                                            ' {"kind": "box", "subtype": 13, "at": [1, 5, 0]}]')
        self.assertEqual([2, 13], [o.subtype for o in objects])

    def test_a_boxs_subtype_has_to_be_one_the_beach_has(self):
        self.assert_error('[{"kind": "box", "at": [0, 0, 0]}]', "object 1", "subtype")
        self.assert_error('[{"kind": "box", "subtype": 1, "at": [0, 0, 0]}]', "object 1", "subtype", "13")
        self.assert_error('[{"kind": "box", "subtype": 2.5, "at": [0, 0, 0]}]', "object 1", "subtype")

    def test_a_stack_is_at_least_one_box(self):
        self.assert_error('[{"kind": "box", "subtype": 2, "at": [0, 0, 0], "stack": 0}]', "object 1", "stack")
        self.assert_error('[{"kind": "box", "subtype": 2, "at": [0, 0, 0], "stack": 1.5}]', "object 1", "stack")

    def test_only_a_box_takes_a_subtype_or_stack(self):
        self.assert_error('[{"kind": "end", "subtype": 2, "at": [0, 0, 0]}]', "object 1", "subtype")
        self.assert_error('[{"kind": "spawn", "stack": 2, "at": [0, 0, 0]}]', "object 1", "stack")

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



class ToZone(unittest.TestCase):
    def test_blenders_z_is_up_and_y_runs_along_minus_z(self):
        # blender (x, y, z) is the .obj's (x, z, -y)
        self.assertEqual((100, 300, -200), levelobjects.to_zone((1, 2, 3), 100, 0, (0, 0, 0)))

    def test_it_turns_and_moves_as_the_map_does(self):
        self.assertEqual((-200 - 10, 300 - 20, -100 - 30),
                         levelobjects.to_zone((1, 2, 3), 100, 90, (10, 20, 30)))

    def test_it_lands_where_a_vertex_there_does(self):
        # a vertex in the .obj at blender (1.5, -2, 0.25), fitted into a zone
        # with the rest of the map, ends up where to_zone puts the position
        obj = "v 1.5 0.25 2\nv -4 0 -8\nv 4 2 8\nf 1 2 3\n"
        for turn in (0, 90, 180, 270):
            fit = blendmap.fit(blendmap.read_obj(obj, 256, turn), 128, 1024, margin=128, long_z=True)
            at = levelobjects.to_zone((1.5, -2, 0.25), 256, turn, fit.offset)
            for a, b in zip(fit.mesh.verts[0], at):
                self.assertAlmostEqual(a, b, delta=4)


if __name__ == "__main__":
    unittest.main()

import unittest

from editbuffer import (
    AmbiguousTargetError,
    EditBuffer,
    InvalidOperationError,
    Selection,
    StaleVersionError,
    TargetNotFoundError,
    ValidationError,
)
from editbuffer.validators import valid_json


class EditBufferTests(unittest.TestCase):
    def test_append_and_view(self) -> None:
        buffer = EditBuffer("hello")

        buffer.append(" world")

        self.assertEqual(buffer.view(), "hello world")

    def test_exact_replace(self) -> None:
        buffer = EditBuffer("red green blue")

        buffer.replace(Selection.exact("green"), "amber")

        self.assertEqual(buffer.view(), "red amber blue")

    def test_context_replace_disambiguates_repeated_text(self) -> None:
        buffer = EditBuffer("left x middle x right")

        buffer.replace(
            Selection.context(before="middle ", text="x", after=" right"),
            "y",
        )

        self.assertEqual(buffer.view(), "left x middle y right")

    def test_range_replace(self) -> None:
        buffer = EditBuffer("abcdef")

        buffer.replace(Selection.range(1, 4, expected_version=0), "X")

        self.assertEqual(buffer.view(), "aXef")

    def test_delete_and_insert(self) -> None:
        buffer = EditBuffer("alpha beta gamma")

        buffer.insert_before(Selection.exact("beta"), "small ")
        buffer.insert_after(Selection.exact("beta"), " large")
        buffer.delete(Selection.exact("alpha "))

        self.assertEqual(buffer.view(), "small beta large gamma")

    def test_not_found_does_not_mutate(self) -> None:
        buffer = EditBuffer("alpha")

        with self.assertRaises(TargetNotFoundError):
            buffer.replace(Selection.exact("beta"), "gamma")

        self.assertEqual(buffer.view(), "alpha")
        self.assertEqual(len(buffer.history), 0)

    def test_ambiguous_target_requires_disambiguation(self) -> None:
        buffer = EditBuffer("x x")

        with self.assertRaises(AmbiguousTargetError) as error:
            buffer.delete(Selection.exact("x"))

        self.assertEqual(error.exception.candidates, ((0, 1), (2, 3)))
        self.assertEqual(buffer.view(), "x x")

    def test_occurrence_explicitly_selects_duplicate(self) -> None:
        buffer = EditBuffer("x x")

        buffer.replace(Selection.exact("x", occurrence=1), "y")

        self.assertEqual(buffer.view(), "x y")

    def test_overlapping_matches_are_ambiguous(self) -> None:
        buffer = EditBuffer("aaa")

        with self.assertRaises(AmbiguousTargetError) as error:
            buffer.replace(Selection.exact("aa"), "x")

        self.assertEqual(error.exception.candidates, ((0, 2), (1, 3)))
        self.assertEqual(buffer.view(), "aaa")

    def test_history_tracks_successful_operations(self) -> None:
        buffer = EditBuffer("a")

        buffer.append("b")
        buffer.replace(Selection.exact("b"), "c")

        self.assertEqual([record.operation.kind for record in buffer.history], ["append", "replace"])
        self.assertEqual(buffer.history[1].before, "b")
        self.assertEqual(buffer.history[1].after, "c")
        self.assertEqual(buffer.history[1].version_before, 1)
        self.assertEqual(buffer.history[1].version_after, 2)

    def test_commit_closes_buffer(self) -> None:
        buffer = EditBuffer("done")

        self.assertEqual(buffer.commit(), "done")
        self.assertTrue(buffer.committed)
        self.assertEqual(buffer.view(), "done")
        with self.assertRaises(InvalidOperationError):
            buffer.append("!")

    def test_invalid_operation_dictionary(self) -> None:
        buffer = EditBuffer("text")

        with self.assertRaises(InvalidOperationError):
            buffer.apply({"op": "move", "target": {"type": "exact", "text": "text"}})

        self.assertEqual(buffer.view(), "text")

    def test_text_is_required_for_json_replace_operation(self) -> None:
        buffer = EditBuffer("text")

        with self.assertRaises(InvalidOperationError):
            buffer.apply({"op": "replace", "target": {"type": "exact", "text": "text"}})

        self.assertEqual(buffer.view(), "text")

    def test_json_like_operation_uses_core_resolution(self) -> None:
        buffer = EditBuffer("a b")

        buffer.apply(
            {
                "op": "replace",
                "target": {"type": "exact", "text": "b"},
                "text": "c",
            }
        )

        self.assertEqual(buffer.view(), "a c")

    def test_stale_range_is_rejected(self) -> None:
        buffer = EditBuffer("abc")
        buffer.append("d")

        with self.assertRaises(StaleVersionError):
            buffer.delete(Selection.range(0, 1, expected_version=0))

        self.assertEqual(buffer.view(), "abcd")

    def test_validator_failure_is_atomic(self) -> None:
        buffer = EditBuffer('{"ok": true}', validators=(valid_json,))

        with self.assertRaises(ValidationError):
            buffer.replace(Selection.exact("true"), "invalid")

        self.assertEqual(buffer.view(), '{"ok": true}')
        self.assertEqual(len(buffer.history), 0)


if __name__ == "__main__":
    unittest.main()

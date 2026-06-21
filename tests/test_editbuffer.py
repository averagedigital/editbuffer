import unittest

from editbuffer import (
    AmbiguousTargetError,
    EditBuffer,
    FuzzyMatchError,
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

    def test_fuzzy_replace_is_explicit_and_audited(self) -> None:
        buffer = EditBuffer("run integration tests now")

        record = buffer.replace(
            Selection.fuzzy("run integrtion tests", threshold=0.8),
            "run unit tests",
        )

        self.assertEqual(buffer.view(), "run unit tests now")
        self.assertLess(record.confidence, 1.0)

    def test_fuzzy_replace_rejects_close_competing_targets(self) -> None:
        buffer = EditBuffer("install package-a\ninstall package-b")

        with self.assertRaises(FuzzyMatchError) as error:
            buffer.replace(
                Selection.fuzzy(
                    "install package-c",
                    threshold=0.8,
                    ambiguity_margin=0.1,
                ),
                "install package-d",
            )

        self.assertEqual(error.exception.reason, "ambiguous")
        self.assertGreaterEqual(len(error.exception.candidates), 2)
        self.assertEqual(buffer.view(), "install package-a\ninstall package-b")

    def test_fuzzy_replace_rejects_low_confidence_target(self) -> None:
        buffer = EditBuffer("unrelated content")

        with self.assertRaises(FuzzyMatchError) as error:
            buffer.delete(Selection.fuzzy("target text", threshold=0.9))

        self.assertEqual(error.exception.reason, "below_threshold")
        self.assertGreater(len(error.exception.candidates), 0)

    def test_fenced_code_block_selection(self) -> None:
        buffer = EditBuffer(
            "before\n```python editbuffer:id=setup\nprint('old')\n```\nafter"
        )

        buffer.replace(Selection.block("setup"), "print('new')\n")

        self.assertEqual(
            buffer.view(),
            "before\n```python editbuffer:id=setup\nprint('new')\n```\nafter",
        )

    def test_markdown_region_block_selection(self) -> None:
        buffer = EditBuffer(
            "before\n<!-- editbuffer:block summary -->\nold\n"
            "<!-- /editbuffer:block -->\nafter"
        )

        buffer.replace(Selection.block("summary"), "new\n")

        self.assertIn("<!-- editbuffer:block summary -->\nnew\n<!-- /editbuffer:block -->", buffer.view())

    def test_duplicate_block_id_is_ambiguous(self) -> None:
        buffer = EditBuffer(
            "``` editbuffer:id=x\na\n```\n``` editbuffer:id=x\nb\n```"
        )

        with self.assertRaises(AmbiguousTargetError):
            buffer.delete(Selection.block("x"))

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

    def test_rollback_restores_snapshot_and_creates_new_version(self) -> None:
        buffer = EditBuffer("a")
        buffer.append("b")
        buffer.append("c")

        buffer.rollback(1)

        self.assertEqual(buffer.view(), "ab")
        self.assertEqual(buffer.version, 3)
        self.assertEqual(buffer.versions, (0, 1, 2, 3))
        self.assertEqual(buffer.history[-1].operation.kind, "rollback")
        self.assertEqual(buffer.history[-1].operation.version, 1)

    def test_rollback_rejects_unknown_version_without_mutation(self) -> None:
        buffer = EditBuffer("a")

        with self.assertRaises(InvalidOperationError):
            buffer.rollback(99)

        self.assertEqual(buffer.view(), "a")
        self.assertEqual(buffer.version, 0)


if __name__ == "__main__":
    unittest.main()

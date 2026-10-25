"""Unit tests for withinfo_helpers (no Senzing SDK required)."""

import unittest

import orjson

from withinfo_helpers import extract_unique_entities, missing_entity_line


class TestMissingEntityLine(unittest.TestCase):
    def test_placeholder_is_valid_json(self):
        # Regression: the placeholder used to be '{ENTITY":{"ENTITY_ID"7,...' (invalid JSON).
        parsed = orjson.loads(missing_entity_line(7))
        self.assertEqual(parsed, {"RESOLVED_ENTITY": {"ENTITY_ID": 7, "RECORDS": []}})

    def test_placeholder_is_single_line(self):
        self.assertNotIn("\n", missing_entity_line(123456789))


class TestExtractUniqueEntities(unittest.TestCase):
    def test_counts_distinct_entities(self):
        # Regression: the "Extracted N unique entities" message always printed 0.
        lines = [
            '{"DATA_SOURCE":"TEST","RECORD_ID":"1","AFFECTED_ENTITIES":[{"ENTITY_ID":1}]}\n',
            '{"DATA_SOURCE":"TEST","RECORD_ID":"2","AFFECTED_ENTITIES":[{"ENTITY_ID":1},{"ENTITY_ID":2}]}\n',
            '{"DATA_SOURCE":"TEST","RECORD_ID":"3","AFFECTED_ENTITIES":[{"ENTITY_ID":3}]}\n',
        ]
        self.assertEqual(extract_unique_entities(lines), {1, 2, 3})

    def test_no_affected_entities(self):
        lines = [
            '{"DATA_SOURCE":"TEST","RECORD_ID":"1","AFFECTED_ENTITIES":[]}\n',
            "\n",
        ]
        self.assertEqual(extract_unique_entities(lines), set())

    def test_invalid_json_raises(self):
        with self.assertRaises(orjson.JSONDecodeError):
            extract_unique_entities(["not json\n"])


if __name__ == "__main__":
    unittest.main()

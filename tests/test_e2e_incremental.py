"""End-to-end test of sz_incremental_withinfo.py against a real Senzing v4 engine.

Requires SENZING_ENGINE_CONFIGURATION_JSON pointing at a configured repository
with the TEST data source registered; skipped otherwise.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

import orjson

SCRIPT = Path(__file__).resolve().parent.parent / "sz_incremental_withinfo.py"

RECORDS = [
    {
        "DATA_SOURCE": "TEST",
        "RECORD_ID": "E2E-1",
        "NAME_FULL": "Robert Smith",
        "DATE_OF_BIRTH": "1980-01-01",
    },
    {
        "DATA_SOURCE": "TEST",
        "RECORD_ID": "E2E-2",
        "NAME_FULL": "Bob Smith",
        "DATE_OF_BIRTH": "1980-01-01",
    },
    {
        "DATA_SOURCE": "TEST",
        "RECORD_ID": "E2E-3",
        "NAME_FULL": "Jane Doe",
        "PHONE_NUMBER": "555-0100",
    },
]


@unittest.skipUnless(
    os.getenv("SENZING_ENGINE_CONFIGURATION_JSON"),
    "SENZING_ENGINE_CONFIGURATION_JSON not set; no Senzing engine available",
)
class TestEndToEnd(unittest.TestCase):
    def test_load_produces_valid_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_file = tmp_path / "input.jsonl"
            out_file = tmp_path / "delta.jsonl"
            info_file = tmp_path / "withinfo.jsonl"
            # unique RECORD_IDs: re-adding identical records affects no entities
            run_id = uuid.uuid4().hex
            records = [
                {**r, "RECORD_ID": f"{r['RECORD_ID']}-{run_id}"} for r in RECORDS
            ]
            in_file.write_text(
                "".join(orjson.dumps(r).decode() + "\n" for r in records)
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "-o",
                    str(out_file),
                    "-i",
                    str(info_file),
                    str(in_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(
                info_file.exists(), "temporary withinfo file must be removed"
            )

            match = re.search(r"Extracted (\d+) unique entities", proc.stdout)
            self.assertIsNotNone(match, proc.stdout)
            extracted = int(match.group(1))

            entity_ids = set()
            for line in out_file.read_text().splitlines():
                entity_ids.add(orjson.loads(line)["RESOLVED_ENTITY"]["ENTITY_ID"])
            self.assertGreater(extracted, 0)
            self.assertEqual(extracted, len(entity_ids))
            self.assertIn(f"Processed total of {extracted} withinfo", proc.stdout)


if __name__ == "__main__":
    unittest.main()

"""Guard the application boundary while moving HEX validation to shared code."""
from pathlib import Path
import tempfile
import unittest
from common.avr import read_hex


class ArtifactTests(unittest.TestCase):
    def read(self, content, limit=4):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'application.hex'
            path.write_text(content, encoding='ascii')
            return read_hex(path, limit)

    def test_original_reset_bytes_and_explicit_boundary(self):
        image = ':0400000001C002C079\n:00000001FF\n'
        self.assertEqual(self.read(image), {0: 1, 1: 0xc0, 2: 2, 3: 0xc0})
        with self.assertRaises(ValueError):
            self.read(image, limit=3)

    def test_reject_corruption_overlap_and_foreign_address_space(self):
        data = ':0400000001C002C079\n'
        eof = ':00000001FF\n'
        for image in (data.replace('79', '78') + eof, data + data + eof,
                      data, eof + data, ':020000040001F9\n' + data + eof):
            with self.subTest(image=image), self.assertRaises(ValueError):
                self.read(image)

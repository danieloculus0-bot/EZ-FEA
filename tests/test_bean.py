import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ezfea.bean import send_to_bean_inbox

class BeanTests(unittest.TestCase):
    def test_optional(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(send_to_bean_inbox(Path("not-there")))
    def test_inbox(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            inbox=root/"inbox"
            inbox.mkdir()
            handoff=root/"handoff.json"
            handoff.write_text(json.dumps({"analysis":{"status":"completed","input_sha256":"abc"}}))
            with patch.dict(os.environ,{"EZFEA_BEAN_INBOX":str(inbox)}):
                message=json.loads(send_to_bean_inbox(handoff).read_text())
            self.assertEqual(message["command"],"log_note")
            self.assertEqual(message["from"],"ezfea")
            self.assertIn("experimental_not_validated",message["args"]["text"])

if __name__=="__main__":unittest.main()

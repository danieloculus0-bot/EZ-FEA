"""Optional real BEAN Core CommandInbox integration via its 'log_note' command."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

def send_to_bean_inbox(handoff: Path):
    inbox = os.environ.get("EZFEA_BEAN_INBOX")
    if not inbox:
        return None
    root = Path(inbox).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"BEAN inbox doesn't exist: {root}")
    analysis = json.loads(handoff.read_text(encoding="utf-8"))["analysis"]
    msg = {"command":"log_note", "from":"ezfea", "args":{
        "text": f"EZ-FEA status={analysis['status']}; input_sha256={analysis['input_sha256']}; "
                f"record={handoff.resolve()}; engineering_status=experimental_not_validated"}}
    filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")+"_"+uuid4().hex+".json"
    temp, final = root/(filename+".tmp"), root/filename
    temp.write_text(json.dumps(msg, indent=2)+"\n", encoding="utf-8")
    temp.replace(final)
    return final

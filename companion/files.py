"""Small, bounded file operations with no script or executable interface."""

import os
from pathlib import Path
import tempfile

from .policy import ApprovalRequired, PolicyError

MAX_FILE_BYTES = 1_000_000


def execute_file(tool, args, policy, approved_risk=None):
    if tool == "file.list":
        path = policy.check(args["path"], allow_root=True)
        if not path.is_dir():
            raise PolicyError("Listing requires a directory.")
        entries = []
        for entry in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            try:
                safe = policy.check(str(entry))
            except PolicyError:
                continue
            entries.append({"name": entry.name, "is_directory": safe.is_dir()})
            if len(entries) >= 500:
                break
        return {"entries": entries, "limit": 500}
    if tool == "file.read":
        path = policy.check(args["path"])
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise PolicyError("Read requires a regular UTF-8 file no larger than 1 MB.")
        with path.open("rb") as source:
            content = source.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise PolicyError("File exceeds 1 MB.")
        return {"content": content.decode("utf-8"), "path": str(path)}
    if tool == "file.write":
        path = policy.check(args["path"])
        content = args.get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise PolicyError("Write requires UTF-8 content no larger than 1 MB.")
        if not path.parent.is_dir():
            raise PolicyError("The destination folder must already exist.")
        overwrite = args.get("overwrite", False)
        if not isinstance(overwrite, bool):
            raise PolicyError("overwrite must be a boolean.")
        if path.exists() and not overwrite:
            raise PolicyError("The file exists; explicit overwrite is required.")
        if path.exists() and not path.is_file():
            raise PolicyError("Only regular files can be replaced.")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".lilyleo-", delete=False) as target:
                temporary = Path(target.name)
                target.write(content.encode("utf-8"))
                target.flush()
                os.fsync(target.fileno())
            policy.check(str(path))
            if overwrite:
                os.replace(temporary, path)
            else:
                # An atomic hard link fails if another process creates the target.
                os.link(temporary, path)
                temporary.unlink()
            return {"path": str(path), "bytes": len(content.encode("utf-8"))}
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
    if tool == "file.move":
        source = policy.check(args["source"])
        destination = policy.check(args["destination"])
        if not source.is_file() or not destination.parent.is_dir():
            raise PolicyError("Move requires a regular file and an existing destination folder.")
        if destination.exists():
            raise PolicyError("Move never replaces an existing destination.")
        # Same-volume hard link prevents an overwrite race. Cross-volume moves
        # deliberately fail rather than becoming a partly completed copy/delete.
        os.link(source, destination)
        source.unlink()
        return {"source": str(source), "destination": str(destination)}
    if tool == "file.delete":
        path = policy.check(args["path"])
        if approved_risk != "permanent_delete":
            raise ApprovalRequired("permanent_delete")
        if not path.is_file():
            raise PolicyError("Deletion is limited to one regular file; recursive deletion is unavailable.")
        path.unlink()
        return {"deleted": str(path)}
    raise PolicyError("Unknown file tool.")

"""Run one control through the cabinet API exactly as a manager would.

Usage:
  python scripts/cabinet_control.py BRIEF.json OUT_DIR [--uploads SPEC.json]
         [--base-url https://app.thesica.co] [--credentials ~/.thesica/control1.env]
         [--poll-seconds 20] [--max-minutes 90]

Steps (all standard routes, nothing else): POST /auth/login ->
POST /documents/ -> POST /documents/{id}/sources/upload for every PDF of the
spec and PATCH its metadata (title, authors, year, mandatory) ->
GET/POST task-contract/confirm -> POST /generate/full-document (mode=start) ->
GET /jobs/document/{id}/status until a terminal state -> GET
/documents/{id}/export/docx and download the file. Writes OUT_DIR/run.json
with every response that matters (ids, job status history, artifact SHA-256
from the job result, SHA-256 of the downloaded export) and never prints the
password. The job's own artifact (result.docx.sha256) is the file of record;
the export route re-renders the same content and is kept for convenience.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip("'\"")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--uploads", type=Path)
    parser.add_argument("--base-url", default="https://app.thesica.co")
    parser.add_argument(
        "--credentials", type=Path, default=Path.home() / ".thesica" / "control1.env"
    )
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--max-minutes", type=int, default=90)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    creds = read_env(args.credentials)
    brief = json.loads(args.brief.read_text())
    uploads = json.loads(args.uploads.read_text()) if args.uploads else []
    run = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "login": creds.get("CONTROL_LOGIN"),
        "brief": brief,
        "uploads": [],
        "status_history": [],
    }
    api = args.base_url.rstrip("/") + "/api/v1"
    with httpx.Client(timeout=120, follow_redirects=False) as client:
        token = client.post(
            f"{api}/auth/login",
            json={
                "username": creds["CONTROL_LOGIN"],
                "password": creds["CONTROL_PASSWORD"],
            },
        )
        token.raise_for_status()
        client.headers["Authorization"] = "Bearer " + token.json()["access_token"]
        created = client.post(f"{api}/documents/", json=brief)
        created.raise_for_status()
        document_id = created.json()["id"]
        run["document_id"] = document_id
        for spec in uploads:
            pdf = Path(spec["pdf"])
            if not pdf.exists():
                pdf = args.uploads.parent / spec["pdf"]
            data = pdf.read_bytes()
            with_file = client.post(
                f"{api}/documents/{document_id}/sources/upload",
                files={"file": (pdf.name, data, "application/pdf")},
            )
            with_file.raise_for_status()
            row = with_file.json()
            patched = client.patch(
                f"{api}/documents/{document_id}/sources/files/{row['id']}",
                json={
                    "title": spec["title"],
                    "authors": "; ".join(spec["authors"]),
                    "year": int(spec["year"]),
                    "mandatory": bool(spec.get("mandatory")),
                },
            )
            patched.raise_for_status()
            run["uploads"].append(
                {
                    "key": spec["key"],
                    "file": pdf.name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "file_id": row["id"],
                    "citation_key": patched.json().get(
                        "citation_key", row["citation_key"]
                    ),
                    "pages": row["page_count"],
                    "status": patched.json().get("status", row["status"]),
                    "metadata_incomplete": patched.json().get("metadata_incomplete"),
                }
            )
        contract = client.get(f"{api}/documents/{document_id}/task-contract")
        contract.raise_for_status()
        run["task_contract"] = contract.json()
        confirmed = client.post(f"{api}/documents/{document_id}/task-contract/confirm")
        confirmed.raise_for_status()
        run["task_contract_confirmed"] = confirmed.json()
        started = client.post(
            f"{api}/generate/full-document",
            json={"document_id": document_id, "mode": "start"},
        )
        started.raise_for_status()
        run["start_response"] = started.json()
        job_id = started.json().get("job_id")
        run["job_id"] = job_id
        (args.output / "run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=1)
        )
        deadline = time.time() + args.max_minutes * 60
        last = None
        while time.time() < deadline:
            status = client.get(f"{api}/jobs/document/{document_id}/status")
            status.raise_for_status()
            row = status.json() or {}
            snapshot = {
                k: row.get(k)
                for k in (
                    "job_id",
                    "status",
                    "stage",
                    "sections_done",
                    "sections_total",
                    "cost_cents_so_far",
                    "tokens_so_far",
                    "warnings_count",
                    "last_signal",
                )
            }
            if snapshot != last:
                snapshot["at"] = datetime.now(UTC).isoformat()
                run["status_history"].append(snapshot)
                print(json.dumps(snapshot, ensure_ascii=False), flush=True)
                (args.output / "run.json").write_text(
                    json.dumps(run, ensure_ascii=False, indent=1)
                )
                last = {k: v for k, v in snapshot.items() if k != "at"}
            if row.get("status") in {"completed", "failed", "cancelled"}:
                run["final_status"] = row
                break
            time.sleep(args.poll_seconds)
        else:
            run["final_status"] = {"status": "timeout"}
        result = (run.get("final_status") or {}).get("result") or {}
        run["artifact"] = result.get("docx")
        if (run["final_status"] or {}).get("status") == "completed":
            export = client.get(f"{api}/documents/{document_id}/export/docx")
            export.raise_for_status()
            url = export.json()["download_url"]
            if url.startswith("/"):
                url = args.base_url.rstrip("/") + url
            blob = client.get(url)
            blob.raise_for_status()
            path = (
                args.output / f"CABINET-DOCUMENT-{document_id}-JOB-{job_id}.export.docx"
            )
            path.write_bytes(blob.content)
            run["export_download"] = {
                "path": str(path),
                "sha256": hashlib.sha256(blob.content).hexdigest(),
                "bytes": len(blob.content),
            }
    run["finished_at"] = datetime.now(UTC).isoformat()
    (args.output / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1))
    print(
        json.dumps(
            {
                k: run.get(k)
                for k in ("document_id", "job_id", "artifact", "export_download")
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0 if (run.get("final_status") or {}).get("status") == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())

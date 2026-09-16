#!/bin/bash
# Usage: dump_full.sh DOC_ID OUT.json.gz — full recording of one document from the production DB (all provenance rows incl. dependency payloads).
set -euo pipefail
D="$1"; OUT="$2"
cat > /tmp/dumpfull-$D.sql <<SQL
\\t on
\\a
select json_build_object(
 'origin', 'server-dump-2026-09-16',
 'document_id', $D,
 'documents', (select json_agg(row_to_json(d)) from (select id, user_id, title, topic, work_type, language, target_pages, citation_style, status, created_at from documents where id=$D) d),
 'ai_generation_jobs', (select json_agg(row_to_json(j) order by id) from (select id, document_id, status, progress, total_tokens, cost_cents, attempt_count, started_at, completed_at, request_payload from ai_generation_jobs where document_id=$D) j),
 'document_sections', (select json_agg(row_to_json(s) order by section_index) from (select id, document_id, section_index, section_type, status, title, content, word_count from document_sections where document_id=$D) s),
 'document_provenance', (select json_agg(json_build_object('id', id, 'stage', stage, 'event_type', event_type, 'payload', payload, 'created_at', created_at) order by id) from document_provenance where document_id=$D)
);
SQL
ssh -o ConnectTimeout=30 thesica "docker exec -i ai-thesis-postgres sh -c 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -q'" < /tmp/dumpfull-$D.sql | gzip -c > "$OUT"
python3 -c "
import gzip, json, sys
from collections import Counter
d=json.loads(gzip.decompress(open('$OUT','rb').read()))
ev=d['document_provenance'] or []
print('doc', $D, '| events', len(ev), '| deps', Counter((e['payload'] or {}).get('kind') for e in ev if e['event_type']=='generation_dependency').most_common(8), '| bytes', __import__('os').path.getsize('$OUT'))"

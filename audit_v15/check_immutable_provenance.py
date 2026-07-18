import json
from pathlib import Path
from datetime import datetime
import hashlib
from typing import Dict, Tuple

class ProvenanceError(Exception):
    pass

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def verify_immutable_provenance(root_dir: Path) -> Dict[str, Tuple[bool, str]]:
    results: Dict[str, Tuple[bool, str]] = {}
    v15_dir = root_dir / 'v15_seven_day_robustness'
    lock_path = v15_dir / 'V15_PRE_RESULT_LOCK.json'
    manifest_path = root_dir / 'SHA256SUMS.txt'
    post_manifest = v15_dir / 'V15_POST_RESULT_SHA256SUMS.txt'
    
    # 1. Manifest Integrity
    try:
        if not manifest_path.is_file():
            raise ProvenanceError("SHA256SUMS.txt does not exist.")
        manifest_lines = manifest_path.read_text(encoding='utf-8').splitlines()
        manifest_hashes = {}
        for line in manifest_lines:
            if line.strip():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    if parts[1].strip() in manifest_hashes:
                        raise ProvenanceError(f"Duplicate path in manifest: {parts[1].strip()}")
                    manifest_hashes[parts[1].strip()] = parts[0]
        results['checksum_manifest_integrity'] = (True, "Parsed SHA256SUMS.txt")
    except Exception as e:
        results['checksum_manifest_integrity'] = (False, str(e))
        raise ProvenanceError(str(e))
        
    # 2. Lock Schema & Timestamp
    try:
        if not lock_path.is_file():
            raise ProvenanceError("V15_PRE_RESULT_LOCK.json does not exist.")
        lock_data = json.loads(lock_path.read_text(encoding='utf-8'))
        results['lock_schema_validity'] = (True, "Parsed lock JSON")
        created_utc = lock_data['created_utc']
        dt = datetime.fromisoformat(created_utc)
        if dt.tzinfo is None:
            raise ProvenanceError("created_utc is not timezone-aware.")
        results['lock_timestamp_validity'] = (True, created_utc)
    except Exception as e:
        if 'lock_schema_validity' not in results:
            results['lock_schema_validity'] = (False, str(e))
        if 'lock_timestamp_validity' not in results:
            results['lock_timestamp_validity'] = (False, str(e))
        raise ProvenanceError(str(e))
        
    # 3. Locked Pre-Result Inputs
    all_inputs_ok = True
    for item in lock_data.get('files', []):
        name = f"lock_{item['path'].replace('/', '_').replace('.', '_')}"
        try:
            p = root_dir / item['path']
            rel_path = f"./{item['path']}"
            if not p.is_file():
                raise ProvenanceError(f"Locked input missing: {item['path']}")
            actual_hash = sha256(p)
            if actual_hash != item['sha256']:
                raise ProvenanceError(f"Hash mismatch: {item['path']}")
            if rel_path not in manifest_hashes:
                raise ProvenanceError(f"Not in SHA256SUMS.txt: {item['path']}")
            if manifest_hashes[rel_path] != actual_hash:
                raise ProvenanceError(f"SHA256SUMS.txt mismatch: {item['path']}")
            results[name] = (True, "Verified")
        except Exception as e:
            results[name] = (False, str(e))
            all_inputs_ok = False
            
    # 4. Required Final Artifacts
    try:
        if not post_manifest.is_file():
            raise ProvenanceError("V15_POST_RESULT_SHA256SUMS.txt missing")
        post_lines = post_manifest.read_text(encoding='utf-8').splitlines()
        for line in post_lines:
            if line.strip():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    if parts[1].strip() == "V15_EXECUTION.log":
                        continue # Removed in Branch B
                    artifact_rel = f"v15_seven_day_robustness/{parts[1].strip()}"
                    p = root_dir / artifact_rel
                    full_rel = f"./{artifact_rel}"
                    if not p.is_file():
                        raise ProvenanceError(f"Final artifact missing: {artifact_rel}")
                    actual_hash = sha256(p)
                    if full_rel not in manifest_hashes:
                        raise ProvenanceError(f"Final artifact not in SHA256SUMS.txt: {artifact_rel}")
                    if manifest_hashes[full_rel] != actual_hash:
                        raise ProvenanceError(f"Final artifact hash mismatch in SHA256SUMS.txt: {artifact_rel}")
        results['required_final_artifact_integrity'] = (True, "All post-result artifacts verified")
    except Exception as e:
        results['required_final_artifact_integrity'] = (False, str(e))
        all_inputs_ok = False
        
    results['immutable_provenance_integrity'] = (all_inputs_ok, "Aggregate of inputs and final artifacts")
    
    return results

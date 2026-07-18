#!/usr/bin/env python3
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    git_cmd = r'C:\Program Files\Git\cmd\git.exe' if os.name == 'nt' else 'git'
    try:
        root_out = subprocess.run([git_cmd, 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True)
        repo_root = Path(root_out.stdout.strip())
    except Exception as e:
        sys.exit(f"Failed to find git root: {e}")

    try:
        ls_out = subprocess.run([git_cmd, 'ls-files', '-z'], cwd=repo_root, capture_output=True, check=True)
        raw_files = ls_out.stdout.split(b'\0')
        # Remove the trailing empty element if present
        if raw_files and raw_files[-1] == b'':
            raw_files.pop()
    except Exception as e:
        sys.exit(f"Failed to run git ls-files: {e}")

    manifest_entries = []
    seen = set()

    for bf in raw_files:
        try:
            rel_str = bf.decode('utf-8')
        except UnicodeDecodeError:
            sys.exit(f"File path is not valid UTF-8: {bf}")

        rel_str = rel_str.replace('\\', '/')
        if rel_str == "SHA256SUMS.txt":
            continue

        if rel_str in seen:
            sys.exit(f"Duplicate normalized path detected: {rel_str}")
        seen.add(rel_str)

        if rel_str.startswith('/') or '..' in rel_str.split('/'):
            sys.exit(f"Invalid path traversal or absolute path detected: {rel_str}")

        p = repo_root / rel_str
        if p.is_symlink():
            sys.exit(f"Symlinks are not permitted in the checksum manifest: {rel_str}")
        
        if not p.is_file():
            sys.exit(f"Tracked path is not a regular file: {rel_str}")

        h = hashlib.sha256()
        try:
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
        except Exception as e:
            sys.exit(f"Failed to open or read file '{rel_str}': {e}")
        
        manifest_entries.append(f"{h.hexdigest()}  ./{rel_str}")

    manifest_entries.sort()
    
    target_manifest = repo_root / "SHA256SUMS.txt"
    try:
        fd, temp_path = tempfile.mkstemp(dir=repo_root, prefix=".SHA256SUMS.tmp")
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(manifest_entries) + '\n')
        os.replace(temp_path, target_manifest)
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        sys.exit(f"Failed to write manifest atomically: {e}")

if __name__ == '__main__':
    main()

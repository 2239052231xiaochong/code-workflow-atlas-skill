#!/usr/bin/env python3
"""Create a deterministic skill ZIP and adjacent SHA-256 file."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def package(skill, output):
    skill = skill.resolve()
    if not (skill / 'SKILL.md').is_file():
        raise ValueError('Skill directory must contain SKILL.md')
    if output.resolve().is_relative_to(skill):
        raise ValueError('Write release archives outside the skill directory')
    files = sorted(p for p in skill.rglob('*') if p.is_file() and not any(
        part in {'.git', '__pycache__', '.pytest_cache', 'node_modules'} for part in p.relative_to(skill).parts
    ) and p.suffix not in {'.pyc', '.zip'})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            if file.is_symlink():
                raise ValueError('Do not package symlinks')
            name = skill.name + '/' + file.relative_to(skill).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, file.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n', encoding='utf-8')
    return digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(package(args.skill, args.output))

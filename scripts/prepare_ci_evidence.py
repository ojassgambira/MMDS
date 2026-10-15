"""Publish only allowlisted aggregate evidence, never datasets/models or arbitrary logs."""
import argparse
import os
from pathlib import Path
from mmd_fraud.diagnostics import redact

ALLOWED = ('pytest.log', 'generated-report.md', 'generated-execution.json', 'real-release.json')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ALLOWED:
        path = args.directory / name
        if path.is_file():
            # Inputs are produced by our fixture tests or aggregate real validation only.
            content = path.read_text()
            clean = redact(content)
            (args.output / name).write_text(clean)
            if name.endswith('.md') or name == 'real-release.json':
                summary = os.environ.get('GITHUB_STEP_SUMMARY')
                if summary:
                    with Path(summary).open('a') as handle:
                        handle.write(f'\n## {name}\n\n' + clean + '\n')

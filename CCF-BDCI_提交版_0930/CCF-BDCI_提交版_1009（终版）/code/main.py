#!/usr/bin/env python3
"""Portable entry point for the submitted paper pipeline and DeepAgent experiments."""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
CODE = Path(__file__).resolve().parent
BUNDLE = CODE.parent
PROJECT = CODE / 'project'
SWARM = PROJECT / 'jiuwenswarm'
SCRIPTS = SWARM / 'research-paper-generator' / 'scripts'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', default='replay',
                        choices=['replay', 'live', 'experiment', 'image', 'test', 'verify', 'manifest'])
    parser.add_argument('--output', type=Path, help='New run directory, or JSON report path for verify')
    parser.add_argument('--config', type=Path, help='Override the mode-specific configuration')
    parser.add_argument('--env-file', type=Path, help='Private credential file outside the submission')
    parser.add_argument('--model', help='Override the writing model for live mode')
    parser.add_argument('--no-compile', action='store_true', help='Render source without PDF compilation')
    parser.add_argument('--self-test', action='store_true', help='Experiment only: use a fake model')
    parser.add_argument('--max-cases', type=int, default=1, help='Experiment questions; 0 means all 20')
    parser.add_argument('--context-chars', type=int, default=600)
    parser.add_argument('--generate-methodology', action='store_true', help='Live mode: create a new DashScope image')
    args = parser.parse_args()
    if args.mode in {'verify', 'manifest'}:
        from bundle_check import verify, write_manifest
        if args.mode == 'manifest':
            write_manifest(BUNDLE)
            print('Updated SHA256SUMS.txt; run verify to check submission readiness.')
            return 0
        return verify(BUNDLE, args.output)

    # Put the submitted source first, even if the original repository is installed editable.
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(SWARM), str(SWARM / 'jiuwenbox' / 'src')])
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'

    def run(script: Path, *arguments: object):
        subprocess.run([sys.executable, '-B', str(script), *(str(a) for a in arguments)],
                       cwd=PROJECT, env=env, check=True)

    try:
        if args.mode == 'test':
            return subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s',
                                   str(SWARM / 'research-paper-generator' / 'tests'), '-v'],
                                  cwd=PROJECT, env=env).returncode
        output = (args.output or (BUNDLE.parent / 'CCF-BDCI_runs' /
                  (args.mode + '-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f')))).resolve()
        if output.exists():
            parser.error('Output already exists; choose a new directory.')
        if output.is_relative_to(BUNDLE):
            parser.error('Keep generated output outside the submission directory.')
        extra = [] if args.no_compile else ['--compile']
        if args.mode == 'replay':
            examples = SCRIPTS.parent / 'examples'
            run(SCRIPTS / 'generate_framework.py', '--brief', examples / 'memory-research.brief.json',
                '--literature', examples / 'memory-research.literature.json', '--output', output / 'framework')
            run(SCRIPTS / 'fill_content.py', output / 'framework', '--content-json',
                BUNDLE / 'evidence/writing_run/content.json', '--output', output / 'paper', *extra)
        elif args.mode == 'image':
            image_args = ['--env-file', args.env_file.resolve()] if args.env_file else []
            if args.model: image_args += ['--model', args.model]
            run(SCRIPTS / 'generate_methodology.py', '--config', (args.config or CODE / 'config.yaml').resolve(), '--output', output / 'methodology.png', *image_args)
        elif args.mode == 'live':
            config = (args.config or CODE / 'config.yaml').resolve()
            if args.env_file:
                extra += ['--env-file', args.env_file.resolve()]
            if args.model:
                extra += ['--model', args.model]
            if args.generate_methodology:
                extra += ['--generate-methodology']
            run(SCRIPTS / 'write_paper.py', '--config', config, '--output', output, *extra)
        else:
            if args.max_cases < 0 or args.context_chars <= 0:
                parser.error('max-cases must be nonnegative and context-chars must be positive.')
            output.mkdir(parents=True)
            env['JIUWENSWARM_DATA_DIR'] = str(output / '.runtime')
            config = (args.config or CODE / 'config.experiment.yaml').resolve()
            extra = ['--self-test'] if args.self_test else []
            if args.env_file:
                extra += ['--env-file', args.env_file.resolve()]
            run(SWARM / 'experiments/longmemeval_turn20_ab.py', '--config', config,
                '--max-cases', args.max_cases, '--context-chars', args.context_chars,
                '--output', output / 'results.json', *extra)
        print(f'Output: {output}')
        return 0
    except subprocess.CalledProcessError as error:
        return error.returncode or 1


if __name__ == '__main__':
    raise SystemExit(main())

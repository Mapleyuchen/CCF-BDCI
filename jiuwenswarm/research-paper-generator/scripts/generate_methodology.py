#!/usr/bin/env python3
"""Generate a method PNG with DashScope's asynchronous image API; no local model or Codex required."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import yaml
from paper_content.model import resolve_env


def _json_request(request):
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        status = error.code
        try:
            code = json.load(error).get('code', 'provider_error')
        except (ValueError, AttributeError, TypeError):
            code = 'provider_error'
        finally:
            error.close()
        # Never expose a provider message, signed URL or credential in errors.
        hints = {'AllocationQuota.FreeTierOnly': 'Free quota exhausted and paid calls disabled',
                 'InvalidApiKey': 'API key is invalid for this region',
                 'InvalidParameter': 'Check model and image dimensions',
                 'InvalidParameter.Model': 'Image model is unavailable to this account',
                 'ModelNotFound': 'Image model is unavailable to this account',
                 'Arrearage': 'DashScope account balance is insufficient'}
        raise ValueError(f'Image API HTTP {status}: {hints.get(code, "check account quota, model and region")}') from None


def generate(config_path: Path, output: Path, *, prompt_path=None, model=None, force=False, resume_task=None):
    config = resolve_env(yaml.safe_load(config_path.read_text(encoding='utf-8-sig')) or {})
    settings = config.get('images') or {}
    if settings.get('provider', 'dashscope') != 'dashscope':
        raise ValueError('This image pipeline uses DashScope only')
    key = settings.get('api_key', '')
    if not key:
        raise ValueError('Missing DASHSCOPE_API_KEY in the process environment')
    base = settings.get('base_url', 'https://dashscope.aliyuncs.com/api/v1').rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query:
        raise ValueError('images.base_url must be HTTPS without credentials or query parameters')
    model = model or settings.get('model', 'qwen-image-3.0-pro')
    if resume_task and not re.fullmatch(r'[A-Za-z0-9-]{8,100}', resume_task):
        raise ValueError('Invalid task ID')
    prompt_path = Path(prompt_path) if prompt_path else config_path.parent / settings.get('prompt_file', '../prompts/methodology.txt')
    prompt = prompt_path.read_text(encoding='utf-8').strip()
    if not prompt:
        raise ValueError('Methodology prompt is empty')
    output = output.resolve()
    report_path = output.with_suffix('.provenance.json')
    if not force and (output.exists() or report_path.exists()):
        raise ValueError('Output or provenance already exists; choose a new path or explicitly use --force')
    if output.suffix.lower() != '.png':
        raise ValueError('Output must have a .png extension')
    parameters = {'size': settings.get('size', '2688*1536'), 'n': 1,
                  'prompt_extend': settings.get('prompt_extend', False), 'watermark': settings.get('watermark', False)}
    payload = {'model': model, 'input': {'messages': [{'role': 'user', 'content': [{'text': prompt}]}]},
               'parameters': parameters}
    endpoint = base + '/services/aigc/image-generation/generation'
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'X-DashScope-Async': 'enable'}
    report = {'schema_version': 1, 'provider': 'dashscope-image-api', 'endpoint': endpoint,
              'requested_model': model, 'request_settings': parameters,
              'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'status': 'running',
              'create_attempts': 0 if resume_task else 1, 'polls': 0,
              'note': 'Conceptual method illustration. Experimental plots are computed separately from records.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    def save():
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        if resume_task:
            report['task_id'] = resume_task
        else:
            response = _json_request(Request(endpoint, data=json.dumps(payload).encode(), headers=headers))
            report['task_id'] = response['output']['task_id']
            report['request_id'] = response.get('request_id')
        save()
        print(f"Image task accepted: {report['task_id']}; polling the existing task", flush=True)
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            response = _json_request(Request(base + '/tasks/' + report['task_id'], headers={'Authorization': 'Bearer ' + key}))
            report['polls'] += 1
            result = response['output']
            report['task_status'] = result['task_status']
            save()
            if result['task_status'] == 'SUCCEEDED':
                urls = [item['url'] for item in result.get('results', []) if item.get('url')]
                for choice in result.get('choices', []):
                    urls += [item['image'] for item in choice.get('message', {}).get('content', []) if item.get('image')]
                if not urls or urlparse(urls[0]).scheme != 'https':
                    raise ValueError('Image task completed without an HTTPS image result')
                # Signed object URL is temporary; download immediately without forwarding the API key.
                with urlopen(urls[0], timeout=120) as downloaded:
                    raw = downloaded.read()
                if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Image result is not a PNG')
                output.write_bytes(raw)
                report.update(status='completed', image_sha256=hashlib.sha256(raw).hexdigest(),
                              bytes=len(raw), usage=response.get('usage'))
                break
            if result['task_status'] in ('FAILED', 'CANCELED', 'UNKNOWN'):
                raise ValueError('Image task did not succeed; check DashScope task records and account quota')
            time.sleep(5)
        else:
            raise ValueError('Polling timed out; resume the saved task ID instead of creating another paid task')
    except (URLError, TimeoutError, OSError):
        report.update(status='failed', error_code='connection_failed')
        raise ValueError('Image connection failed; resume saved task ID if available, billing status may be unknown') from None
    except (ValueError, KeyError, IndexError, TypeError) as error:
        report.update(status='failed', error_code='api_or_response_error')
        if isinstance(error, ValueError):
            raise
        raise ValueError('Image API returned an unexpected response; inspect task status before retrying') from None
    finally:
        save()
    return report


def main():
    module = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=module/'examples/dashscope-research.yaml')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prompt', type=Path)
    parser.add_argument('--model')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--resume-task', help='Poll an already-created task; does not submit another paid generation')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        if not args.env_file.is_file(): parser.error('Environment file does not exist')
        load_dotenv(args.env_file, override=True)
    try:
        report = generate(args.config, args.output, prompt_path=args.prompt, model=args.model,
                          force=args.force, resume_task=args.resume_task)
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    print(f"Image saved: {args.output.resolve()} ({report['bytes']} bytes); inspect labels before publication")


if __name__ == '__main__': main()

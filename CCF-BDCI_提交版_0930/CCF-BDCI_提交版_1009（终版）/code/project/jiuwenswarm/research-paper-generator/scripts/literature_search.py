#!/usr/bin/env python3
"""Public arXiv metadata retrieval with caching, rate limiting and provenance."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError
import xml.etree.ElementTree as ET


class ArxivSearcher:
    BASE_URL = 'https://export.arxiv.org/api/query'

    def __init__(self, config=None, cache_dir=Path('output/arxiv-cache')):
        config = config or {}
        self.url = config.get('api_url', self.BASE_URL)
        if urlparse(self.url).scheme != 'https' or urlparse(self.url).hostname not in {'export.arxiv.org', 'arxiv.org'}:
            raise ValueError('Use the official HTTPS arXiv metadata endpoint')
        self.user_agent = config.get('user_agent', 'CCF-BDCI-PaperResearch/2.0')
        self.interval = max(3.0, float(config.get('interval_seconds', 3.1)))
        self.timeout = float(config.get('timeout_seconds', 60))
        self.cache = Path(cache_dir)
        self.last_request = 0.0
        self.requests = []

    def _fetch(self, parameters):
        url = self.url + '?' + urlencode(parameters)
        path = self.cache / (hashlib.sha256(url.encode()).hexdigest() + '.xml')
        cached = path.is_file()
        if cached:
            raw = path.read_bytes()
        else:
            for attempt in range(3):
                time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                try:
                    with urlopen(Request(url, headers={'User-Agent': self.user_agent}), timeout=self.timeout) as response:
                        raw = response.read(10_000_000)
                    self._parse_arxiv_response(raw)
                    break
                except (URLError, TimeoutError, OSError):
                    if attempt == 2:
                        raise ValueError('arXiv request failed; check network/proxy or use cached metadata') from None
                    time.sleep(self.interval * (attempt + 1))
            self.cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.requests.append({'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                              'from_cache': cached, 'atom_sha256': hashlib.sha256(raw).hexdigest()})
        return self._parse_arxiv_response(raw)

    def search(self, query, max_results=20, start=0):
        if not query or not 1 <= max_results <= 200:
            raise ValueError('Supply a query and max_results between 1 and 200')
        query = query if re.search(r'\b(?:all|ti|au|abs|cat):', query) else 'all:"' + query.replace('"', '') + '"'
        return self._fetch({'search_query': query, 'start': start, 'max_results': max_results,
                            'sortBy': 'relevance', 'sortOrder': 'descending'})

    def fetch_ids(self, ids):
        if not ids or any(not re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?', x) for x in ids):
            raise ValueError('Supply comma-separated modern arXiv IDs')
        return self._fetch({'id_list': ','.join(ids), 'max_results': len(ids)})

    def _parse_arxiv_response(self, raw):
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            raise ValueError('arXiv returned invalid Atom XML') from None
        papers = []
        for entry in root.findall('a:entry', ns):
            source_id = entry.findtext('a:id', '', ns)
            if '/api/errors' in source_id:
                raise ValueError('arXiv rejected the query')
            arxiv_id = source_id.rsplit('/', 1)[-1]
            if not arxiv_id:
                continue
            published = entry.findtext('a:published', '', ns)
            papers.append({'id': re.sub(r'v\d+$', '', arxiv_id), 'arxiv_id': arxiv_id,
                           'title': ' '.join(entry.findtext('a:title', '', ns).split()),
                           'authors': [a.findtext('a:name', '', ns) for a in entry.findall('a:author', ns)],
                           'published': published, 'year': int(published[:4]),
                           'abstract': ' '.join(entry.findtext('a:summary', '', ns).split()),
                           'url': 'https://arxiv.org/abs/' + arxiv_id,
                           'pdf_url': 'https://arxiv.org/pdf/' + arxiv_id})
        return papers

    def search_multiple_queries(self, queries, max_per_query=10):
        papers = [p for query in queries for p in self.search(query, max_per_query)]
        return list({p['id']: p for p in papers}.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--query')
    group.add_argument('--ids', help='Comma-separated arXiv IDs')
    parser.add_argument('--max-results', type=int, default=20)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--cache-dir', type=Path, default=Path('output/arxiv-cache'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        config = {}
        if args.config:
            import yaml
            config = (yaml.safe_load(args.config.read_text(encoding='utf-8')) or {}).get('arxiv', {})
        searcher = ArxivSearcher(config, args.cache_dir)
        papers = searcher.fetch_ids(args.ids.split(',')) if args.ids else searcher.search(args.query, args.max_results)
        if not papers:
            raise ValueError('No papers returned; an empty search is not a completed literature review')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(papers, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        args.output.with_suffix('.provenance.json').write_text(json.dumps(searcher.requests, indent=2) + '\n', encoding='utf-8')
        print(f'Fetched {len(papers)} sources: {args.output}')
    except (ValueError, OSError) as error:
        parser.exit(2, f'Literature retrieval failed: {error}\n')


if __name__ == '__main__':
    main()

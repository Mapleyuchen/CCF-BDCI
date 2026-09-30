"""Uncertainty semantics, metadata integrity and the expanded real PDF path."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE/'scripts'))
from literature_search import ArxivSearcher
from paper_content.evidence import wilson_interval, normalize_result
from paper_content.project import fill_project
from paper_framework.project import generate_project
from test_content import experiment, PROSE


class ResearchTests(unittest.TestCase):
    def test_wilson_extremes_are_not_zero_uncertainty(self):
        lo, hi = wilson_interval(0, 20)
        self.assertAlmostEqual(lo, 0)
        self.assertAlmostEqual(hi, .161125158, places=7)
        lo, hi = wilson_interval(20, 20)
        self.assertAlmostEqual(lo, .838874842, places=7)
        self.assertAlmostEqual(hi, 1)

    def test_partial_evidence_and_discordant_pairs_remain_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'evidence.json'
            data=experiment()
            data['records'][0]['evidence_recall']=0.0
            path.write_text(json.dumps(data),encoding='utf-8')
            result=normalize_result(path,'trial','Trial')
            self.assertEqual(result['paired_outcomes'],{'both_correct':1,'enhanced_only':1,'baseline_only':0,'both_wrong':0})
            self.assertEqual(result['groups']['baseline']['correct_without_full_evidence'],1)
            self.assertEqual(len(result['observed_cases']),2)

    def test_arxiv_xml_error_never_becomes_a_fake_paper(self):
        searcher=ArxivSearcher()
        with self.assertRaisesRegex(ValueError,'rejected'):
            searcher._parse_arxiv_response('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad</id></entry></feed>')
        with self.assertRaisesRegex(ValueError,'invalid Atom'):
            searcher._parse_arxiv_response('not xml')
        self.assertGreaterEqual(ArxivSearcher({'interval_seconds':.1}).interval,3)

    def test_arxiv_cached_response_does_not_call_network(self):
        import hashlib
        from urllib.parse import urlencode
        with tempfile.TemporaryDirectory() as temporary:
            searcher=ArxivSearcher(cache_dir=Path(temporary))
            params={'id_list':'2307.03172','max_results':1}
            url=searcher.url+'?'+urlencode(params)
            raw='<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2307.03172v3</id><title> A\n Paper </title><published>2023-07-06T00:00:00Z</published><author><name>A Author</name></author><summary>Abstract.</summary></entry></feed>'
            (Path(temporary)/(hashlib.sha256(url.encode()).hexdigest()+'.xml')).write_text(raw,encoding='utf-8')
            with patch('literature_search.urlopen',side_effect=AssertionError('network must not be used')):
                papers=searcher.fetch_ids(['2307.03172'])
            self.assertEqual(papers[0]['title'],'A Paper')
            self.assertEqual(papers[0]['id'],'2307.03172')
            self.assertTrue(searcher.requests[0]['from_cache'])

    @unittest.skipUnless(shutil.which('pdflatex') and shutil.which('bibtex'),'LaTeX required')
    def test_research_profile_compiles_equations_image_and_appendix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            generate_project(MODULE/'examples/memory-research.brief.json',root/'framework',
                             MODULE/'examples/memory-research.literature.json')
            outline=json.loads((root/'framework/outline.json').read_text(encoding='utf-8'))
            content={'sections':[]}
            for s in outline['sections']:
                children=[]
                for child in s['subsections']:
                    prose=PROSE+' '+ ' '.join('[[cite:'+k+']]' for k in child['citation_keys'])
                    for eid in child.get('evidence_ids',[]): prose+=' Accuracy was [[metric:'+eid+'.baseline.accuracy]].'
                    children.append({'id':child['id'],'paragraphs':[prose]})
                content['sections'].append({'id':s['id'],'paragraphs':[PROSE],'subsections':children})
            saved=root/'content.json'
            saved.write_text(json.dumps(content),encoding='utf-8')
            report=fill_project(root/'framework',root/'paper',content_json=saved,compile_pdf=True)
            quality=json.loads((root/'paper/quality_report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['status'],'completed',quality)
            self.assertTrue((root/'paper/appendix.tex').is_file())
            self.assertTrue((root/'paper/figures/methodology.png').is_file())
            self.assertIn('question_audit.pdf',report['figures'])
            self.assertEqual(report['calls'],[])


if __name__=='__main__': unittest.main()

from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from generate_methodology import generate

def reply(value): return BytesIO(json.dumps(value).encode())

class ImageApiTests(unittest.TestCase):
    def setup_files(self, directory):
        root = Path(directory)
        (root/'prompt.txt').write_text('Draw the audited method.', encoding='utf-8')
        config = root/'settings.yaml'
        config.write_text('images:\n  api_key: ${DASHSCOPE_API_KEY}\n  prompt_file: prompt.txt\n', encoding='utf-8')
        return config, root/'method.png'

    @patch.dict('os.environ', {'DASHSCOPE_API_KEY': 'unit-test-secret'})
    def test_async_task_download_has_no_forwarded_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            config, output = self.setup_files(directory)
            responses = [reply({'output': {'task_id': 'saved-task-123'}}),
                         reply({'output': {'task_status': 'SUCCEEDED', 'results': [{'url': 'https://result.example/image.png'}]}, 'usage': {'image_count': 1}}),
                         BytesIO(b'\x89PNG\r\n\x1a\nmock-image')]
            with patch('generate_methodology.urlopen', side_effect=responses) as network:
                report = generate(config, output)
            self.assertEqual(network.call_args_list[0].args[0].get_header('Authorization'), 'Bearer unit-test-secret')
            self.assertIsInstance(network.call_args_list[2].args[0], str)
            self.assertEqual(report['status'], 'completed')
            saved = output.with_suffix('.provenance.json').read_text()
            self.assertNotIn('unit-test-secret', saved)
            self.assertNotIn('result.example', saved)
            with self.assertRaisesRegex(ValueError, 'already exists'): generate(config, output)

    @patch.dict('os.environ', {'DASHSCOPE_API_KEY': 'unit-test-secret'})
    def test_quota_failure_stops_without_retry_or_secret_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            config, output = self.setup_files(directory)
            error = HTTPError('https://dashscope.aliyuncs.com',403,'quota',{},reply({'code': 'Arrearage', 'message': 'unit-test-secret'}))
            with patch('generate_methodology.urlopen', side_effect=error) as network:
                with self.assertRaisesRegex(ValueError, 'balance is insufficient'): generate(config, output)
            self.assertEqual(network.call_count, 1)
            self.assertFalse(output.exists())
            self.assertNotIn('unit-test-secret', output.with_suffix('.provenance.json').read_text())

    @patch.dict('os.environ', {'DASHSCOPE_API_KEY': 'unit-test-secret'})
    def test_resume_polls_task_without_creating_another(self):
        with tempfile.TemporaryDirectory() as directory:
            config, output = self.setup_files(directory)
            with patch('generate_methodology.urlopen', return_value=reply({'output': {'task_status': 'FAILED'}})) as network:
                with self.assertRaisesRegex(ValueError, 'did not succeed'): generate(config, output, resume_task='saved-task-123')
            self.assertEqual(network.call_count, 1)
            self.assertTrue(network.call_args.args[0].full_url.endswith('/tasks/saved-task-123'))

if __name__ == '__main__': unittest.main()

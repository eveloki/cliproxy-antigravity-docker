import subprocess
import sys
import unittest
from unittest.mock import patch

from cli_contract import compare, probe


class CLIContractTests(unittest.TestCase):
    def test_cross_stream_order_is_not_a_contract(self):
        # Same CLI output, deliberately emitted in opposite cross-stream order.
        a = probe('stdout first', [sys.executable, '-c', 'import os; os.write(1,b"version\\n"); os.write(2,b"usage\\n")'])
        b = probe('stderr first', [sys.executable, '-c', 'import os; os.write(2,b"usage\\n"); os.write(1,b"version\\n")'])
        compare('help', a, b)

    def test_real_output_changes_are_rejected_in_either_stream(self):
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                a = subprocess.CompletedProcess([], 0, b'version\n', b'usage\n')
                b = subprocess.CompletedProcess([], 0, a.stdout, a.stderr)
                setattr(b, stream, getattr(b, stream) + b'unexpected\n')
                with self.assertRaisesRegex(AssertionError, stream + ' differs'):
                    compare('help', a, b)

    def test_failed_command_reports_status_and_output(self):
        with self.assertRaisesRegex(AssertionError, 'exit=7.*diagnostic'):
            probe('broken', [sys.executable, '-c', 'import sys; print("diagnostic",file=sys.stderr); sys.exit(7)'])

    def test_timeout_is_failure_with_diagnostics(self):
        with patch('cli_contract.subprocess.run', side_effect=subprocess.TimeoutExpired(['docker'], 60, output=b'partial')):
            with self.assertRaisesRegex(AssertionError, 'timed out.*partial'):
                probe('hung', ['docker'])

from unittest import TestCase
import tempfile, os
from backup_monkey import SplunkLogging

class SplunkLoggingTest(TestCase):
  parsed = None
  values = {}
  keys = ['body', 'severity', 'src_account', 'src_role', 'src_region', 'src_volume', 'src_snapshot', 'src_tags', 'subject', 'type', 'category']
  log_file = tempfile.mkstemp()[1]

  @classmethod
  def setUpClass(cls):
    values = dict([(k, k) for k in cls.keys])
    SplunkLogging.set_path(cls.log_file)
    SplunkLogging.write(**values)

    with open(cls.log_file) as f:
      for line in f:
        cls.parsed = dict((k.split(' ')[-1], v.strip()) for k,v in [tuple(kv.split('=')) for kv in line.split(',')])
      f.close()

  def test_write(self):
    assert len(self.parsed.keys()) == len(SplunkLogging.keys)

  def test_reset_invalid_values(self):
    assert self.parsed['type'] == 'unknown'
    assert self.parsed['severity'] == 'unknown'

  def test_values(self):
    for k in filter(lambda v: v not in ['type', 'severity'], self.keys):
      assert self.parsed[k] == k

  def test_no_line_breaks(self):
    SplunkLogging.write(subject='subject\r\n', body='body\ngoes\rhere')
    with open(self.log_file) as f:
      for line in f:
        parsed = dict((k.split(' ')[-1], v) for k,v in [tuple(kv.split('=')) for kv in line.split(',')])
      f.close()
    assert parsed['subject'] == 'subject'
    assert parsed['body'] == 'body goes here'

  @classmethod
  def tearDownClass(cls):
    os.remove(cls.log_file)
    SplunkLogging.reset_path() 

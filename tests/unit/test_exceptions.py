# Copyright 2013 Answers for AWS LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import TestCase
import tempfile, os
from backup_monkey.exception import * 
from backup_monkey import SplunkLogging

class ExceptionTests(TestCase):
    log_file = tempfile.mkstemp()[1]

    @classmethod
    def setUpClass(cls):
        SplunkLogging.set_path(cls.log_file)

    def setUp(self):
        open(self.log_file, 'w').close()
        self.e = BackupMonkeyException('msg', subject='subject', body='body')

    def test_new_exception(self):
        self.assertTrue(isinstance(self.e, BackupMonkeyException))

    def raise_BackupMonkeyException(self):
        raise self.e 
 
    def test_raise_BackupMonkeyException(self):
        self.assertRaises(BackupMonkeyException, self.raise_BackupMonkeyException)

    def test_splunk_logging(self):
        with open(self.log_file) as f:
            for line in f:
                parsed = dict((k.split(' ')[-1], v.strip()) for k,v in [tuple(kv.split('=')) for kv in line.split(',')])
            f.close()
        assert parsed['subject'] == 'subject'
        assert parsed['body'] == 'body'
        assert parsed['type'] == 'alarm'
        assert parsed['severity'] == 'critical'

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.log_file)
        SplunkLogging.reset_path() 

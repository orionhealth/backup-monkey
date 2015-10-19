from backup_monkey.core import BackupMonkey, Logging
from io import StringIO
from unittest import TestCase
import logging
import mock
import re
import sys

class MockStream(StringIO):
    def __init__(self):
    	self.the_stream = []
    def write(self, to_stream):
        self.the_stream.append(to_stream)
    def flush(self):
        pass
    def get(self):
        return self.the_stream
    def clear(self):
        del self.the_stream[:]
    def len(self):
        return len(self.the_stream)

mock_stdout = MockStream()
mock_stderr = MockStream()

class LoggingTest(TestCase):
    stdout = sys.stdout
    stderr = sys.stderr
    log_preamble = "[0-9\-]+ [0-9\:]+ "
    detailed_log_preamble = " \[[a-z0-9\._\(\):]+] "

    def setUp(self):
        sys.stdout = mock_stdout
        sys.stderr = mock_stderr

    def tearDown(self):
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def log_events(self, verbosity, stdout_count, stderr_count):
        mock_stdout.clear()
        assert mock_stdout.len() == 0
        mock_stderr.clear()
        assert mock_stderr.len() == 0
        Logging().configure(verbosity=verbosity, module=__name__)

        log = logging.getLogger(__name__)
        log.debug("This is a Debug Message")
        log.info("This is an Info Message")
        log.warning("This is a Warning Message")
        log.error("This is an Error Message")
        log.critical("This is a Critical Message")

        # Check the number of messages in each mock stream match what was expected
        assert mock_stdout.len() == stdout_count
        assert mock_stderr.len() == stderr_count

    def stream_contains(self, mock_stream, regular_expression):
        for message in mock_stream.get():
            result = re.search(regular_expression, message)
            if result != None:
                return True
        return False

    def stream_does_not_contain(self, mock_stream, regular_expression):
        for message in mock_stream.get():
            result = re.search(regular_expression, message)
            if result != None:
                return False
        return True

    def test_level_0(self):
        # Expectation: Simple error messages with no debug messages
        self.log_events(0, 2, 2)
        assert(self.stream_contains(mock_stdout, "%s\[INFO\] This is an Info Message" % self.log_preamble))
        assert(self.stream_contains(mock_stdout, "%s\[WARNING\] This is a Warning Message" % self.log_preamble))

        assert(self.stream_does_not_contain(mock_stdout, "This is a Debug Message"))
        assert(self.stream_does_not_contain(mock_stdout, "This is a Error Message"))
        assert(self.stream_does_not_contain(mock_stdout, "This is a Critical Message"))

        assert(self.stream_contains(mock_stderr, "%s\[CRITICAL\] This is a Critical Message" % self.log_preamble))
        assert(self.stream_contains(mock_stderr, "%s\[ERROR\] This is an Error Message" % self.log_preamble))

        assert(self.stream_does_not_contain(mock_stderr, "This is a Debug Message"))
        assert(self.stream_does_not_contain(mock_stderr, "This is an Info Message"))
        assert(self.stream_does_not_contain(mock_stderr, "This is a Warning Message"))

    def test_level_1(self):
        # Expectation: Stack info in the error messages with no debug messages
        self.log_events(1, 2, 2)
        assert(self.stream_contains(mock_stdout, "%s\[INFO\]%sThis is an Info Message" % (self.log_preamble, self.detailed_log_preamble)))
        assert(self.stream_contains(mock_stdout, "%s\[WARNING\]%sThis is a Warning Message" % (self.log_preamble, self.detailed_log_preamble)))

        assert(self.stream_does_not_contain(mock_stdout, "This is a Debug Message"))
        assert(self.stream_does_not_contain(mock_stdout, "This is a Error Message"))
        assert(self.stream_does_not_contain(mock_stdout, "This is a Critical Message"))

        assert(self.stream_contains(mock_stderr, "%s\[CRITICAL\]%sThis is a Critical Message" % (self.log_preamble, self.detailed_log_preamble)))
        assert(self.stream_contains(mock_stderr, "%s\[ERROR\]%sThis is an Error Message" % (self.log_preamble, self.detailed_log_preamble)))

        assert(self.stream_does_not_contain(mock_stderr, "This is a Debug Message"))
        assert(self.stream_does_not_contain(mock_stderr, "This is an Info Message"))
        assert(self.stream_does_not_contain(mock_stderr, "This is a Warning Message"))

    def test_level_2(self):
        # Expectation: Stack info in the error messages with debug messages in stdout
        self.log_events(2, 3, 2)
        assert(self.stream_contains(mock_stdout, "%s\[INFO\]%sThis is an Info Message" % (self.log_preamble, self.detailed_log_preamble)))
        assert(self.stream_contains(mock_stdout, "%s\[WARNING\]%sThis is a Warning Message" % (self.log_preamble, self.detailed_log_preamble)))
        assert(self.stream_contains(mock_stdout, "%s\[DEBUG\]%sThis is a Debug Message" % (self.log_preamble, self.detailed_log_preamble)))

        assert(self.stream_does_not_contain(mock_stdout, "This is a Error Message"))
        assert(self.stream_does_not_contain(mock_stdout, "This is a Critical Message"))

        assert(self.stream_contains(mock_stderr, "%s\[CRITICAL\]%sThis is a Critical Message" % (self.log_preamble, self.detailed_log_preamble)))
        assert(self.stream_contains(mock_stderr, "%s\[ERROR\]%sThis is an Error Message" % (self.log_preamble, self.detailed_log_preamble)))

        assert(self.stream_does_not_contain(mock_stderr, "This is a Debug Message"))
        assert(self.stream_does_not_contain(mock_stderr, "This is an Info Message"))
        assert(self.stream_does_not_contain(mock_stderr, "This is a Warning Message"))


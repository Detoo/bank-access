# Copyright (c) The SimpleFIN Team
# See LICENSE for details.
from twisted.trial.unittest import TestCase
from twisted.internet.protocol import ProcessProtocol
from twisted.internet import reactor, defer
from twisted.python.filepath import FilePath
from twisted.python import log

import os
from StringIO import StringIO


class StdinProtocol(ProcessProtocol):
    """
    @ivar done: A Deferred which fires when this protocol is done.
    """

    def __init__(self, responses):
        """
        @param responses: A list of responses to be given in order as stdout
            lines are received.
        """
        self.responses = responses
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.done = defer.Deferred()

    def outReceived(self, data):
        log.msg(repr(data), system='stdout')
        self.stdout.write(data)
        if self.responses:
            r = self.responses.pop(0)
            log.msg(repr(r), system='stdin')
            self.transport.write(r)
            if not self.responses:
                self.transport.closeStdin()

    def errReceived(self, data):
        log.msg(data, system='stderr')
        self.stderr.write(data)

    def processEnded(self, status):
        self.done.callback(status.value.exitCode)


class wrap3Test(TestCase):

    timeout = 2

    def test_basic(self):
        """
        Calling wrap3 should spawn a process that listens on channel 3 for
        prompts and uses the tty to get answers.
        """
        script_file = FilePath(self.mktemp())
        script_file.setContent(
            '#!/usr/bin/env python\n'
            'from banka.prompt import prompt\n'
            'data = prompt("_login")\n'
            'print "got %s" % (data,)\n')

        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.abspath('..')
        env['COVERAGE_PROCESS_START'] = os.path.abspath('../.coveragerc')
        proto = StdinProtocol(['joe\n'])
        reactor.spawnProcess(proto, '../bin/banka',
                             ['banka', 'run', script_file.path],
                             env=env, usePTY=True)

        def check(result):
            stdout_lines = proto.stdout.getvalue().split('\r\n')
            self.assertIn('got joe', stdout_lines)
        return proto.done.addCallback(check)

    def test_error(self):
        """
        If the script exits with exit code 10, it should exit the wrapper with
        exit code 10.
        """
        script_file = FilePath(self.mktemp())
        script_file.setContent(
            '#!/usr/bin/env python\n'
            'import sys\n'
            'sys.exit(10)\n')

        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.abspath('..')
        env['COVERAGE_PROCESS_START'] = os.path.abspath('../.coveragerc')
        proto = StdinProtocol([])
        reactor.spawnProcess(proto, '../bin/banka',
                             ['banka', 'run', script_file.path],
                             env=env)

        def check(result):
            self.assertEqual(result, 10, "Should exit with exit code to "
                             "match the wrapped script")
        return proto.done.addCallback(check)
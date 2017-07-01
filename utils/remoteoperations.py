import os
import sys
import logging
import paramiko
import eventlet
from socket import error as SocketError
from oslo_config import cfg
import subprocess


cache = '/tmp/'
pool = eventlet.greenpool.GreenPool(size=2)

CONF = cfg.CONF

class RemoteConnection(object):

    def __init__(self):
        super(RemoteConnection, self).__init__()
        self.auth = False
        self._curdir = None

    def connect(self, server, username=None, password=None, keyfile=None):

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if username and password:
                self.client.connect(server, username=username, password=password)
            else:
                self.client.connect(server, key_filename=keyfile)

            self.auth = True
            self._curdir = self.curdir()
            #print self._curdir
        except SocketError:
            self.auth = False
        except paramiko.AuthenticationException:
            self.auth = False

    def execute_cmd(self, command, generate=False, get_output=True, timeout=None, stderr=False):
        if not self.auth:
            return ''

        l_o, l_e = open('{}.out'.format(cache), 'w'), open('{}.err'.format(cache), 'w')
        try:
            _,o,e = self.client.exec_command('cd {} && {}'.format(self.curdir(), command), timeout=timeout)
            pool.spawn(lambda infile, outfile: outfile.writelines(line for line in infile), o, l_o)
            pool.spawn(lambda infile, outfile: outfile.writelines(line for line in infile), e, l_e)

        except:
            print 'Error in executing the command %s'%(command)
        pool.waitall()
        l_o.close()
        l_e.close()
        l_o = open('{}.out'.format(cache))
        l_e = open('{}.err'.format(cache))

        if generate:
            if stderr:
                handles = (l_o, l_e)
            else:
                handles = (l_o, )
            return (line.strip() for handle in handles for line in handle)

        errors = l_e.read().strip()
        out = l_o.read().strip()
        if errors:
            pass
            #print 'ERRORs in command'
        l_e.close()
        l_o.close()
        if stderr:
            return '\n'.join((out, errors))
        return out

    def status_command(self, command, timeout=None):
        if not self.auth:
            return ''

        _,o,e = self.client.exec_command('cd {} && {}'.format(self.curdir(), command), timeout=timeout)
        return o.channel.recv_exit_status()

    def curdir(self):
        if self._curdir:
            return self._curdir
        elif self.auth:
            _,o,_ = self.client.exec_command('pwd')
            return o.read().strip()

    def has_dir(self, dirname):
        if dirname == '/':
            return
        dirname = dirname.rstrip('/')
        parent_dir = os.path.dirname(dirname)
        for item in self.execute_cmd('ls -alh {}'.format(parent_dir), generate=True):
            contents = item.split()
            if contents[0][0] == 'd' and os.path.join(parent_dir, contents[8]) == dirname:
                return True
        return False

    def chdir(self, dirname):
        if self.has_dir(dirname):
            if dirname[0] == '/':
                self._curdir = dirname
            else:
                self._curdir = '{}/{}'.format(seld._curdir, dirname)

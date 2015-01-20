#!/usr/bin/env python
# coding:utf-8




import ConfigParser
import os
import sys
import re
import io
import collections
import fnmatch

import logging


try:
    import gevent
    import gevent.socket
    import gevent.server
    import gevent.queue
    import gevent.event
    import gevent.monkey
    gevent.monkey.patch_all(subprocess=True)
except ImportError:
    gevent = None


try:
    import OpenSSL
except ImportError:
    OpenSSL = None

import google_ip



class Common(object):
    """Global Config Object"""

    current_path = os.path.dirname(os.path.abspath(__file__))

    version = current_path.split(os.path.sep)[-2]

    __version__ = version
    google_ip = google_ip.Check_ip()
    python_version = sys.version[:5]

    def __init__(self):
        """load config from proxy.ini"""

        current_path = os.path.dirname(os.path.abspath(__file__))
        ConfigParser.RawConfigParser.OPTCRE = re.compile(r'(?P<option>[^=\s][^=]*)\s*(?P<vi>[=])\s*(?P<value>.*)$')
        self.CONFIG = ConfigParser.ConfigParser()
        self.CONFIG_FILENAME = os.path.abspath( os.path.join(current_path, 'proxy.ini'))
        #os.path.splitext(os.path.abspath(__file__))[0]+'.ini'

        # load ../../../data/goagent/config.ini
        self.CONFIG_USER_FILENAME = os.path.abspath( os.path.join(current_path, os.pardir, os.pardir, os.pardir, 'data', 'goagent', 'config.ini'))

        self.CONFIG.read(self.CONFIG_FILENAME)
        if os.path.isfile(self.CONFIG_USER_FILENAME):
            with open(self.CONFIG_USER_FILENAME, 'rb') as fp:
                content = fp.read()
                if '[gae]' in content:
                    self.CONFIG.remove_section('gae')
                self.CONFIG.readfp(io.BytesIO(content))

        if not self.CONFIG.has_section('http'):
            logging.error('please upgrade your proxy.ini')
            sys.exit(-1)

        self.LISTEN_IP = self.CONFIG.get('listen', 'ip')
        self.LISTEN_PORT = self.CONFIG.getint('listen', 'port')
        self.LISTEN_VISIBLE = self.CONFIG.getint('listen', 'visible')
        self.LISTEN_DEBUGINFO = self.CONFIG.getint('listen', 'debuginfo')

        self.GAE_APPIDS = re.findall(r'[\w\-\.]+', self.CONFIG.get('gae', 'appid').replace('.appspot.com', ''))
        self.GAE_PASSWORD = self.CONFIG.get('gae', 'password').strip()
        self.GAE_PATH = self.CONFIG.get('gae', 'path')
        self.GAE_MODE = "https"
        self.GAE_CRLF = 1
        self.GAE_FETCHSERVER = '%s://%s.appspot.com%s?' % (self.GAE_MODE, self.GAE_APPIDS[0], self.GAE_PATH)



        self.HOSTS_MAP = collections.OrderedDict((k, v or k) for k, v in self.CONFIG.items('hosts') if '\\' not in k and ':' not in k and not k.startswith('.'))
        self.HOSTS_POSTFIX_MAP = collections.OrderedDict((k, v) for k, v in self.CONFIG.items('hosts') if '\\' not in k and ':' not in k and k.startswith('.'))
        self.HOSTS_POSTFIX_ENDSWITH = tuple(self.HOSTS_POSTFIX_MAP)

        self.CONNECT_HOSTS_MAP = collections.OrderedDict((k, v) for k, v in self.CONFIG.items('hosts') if ':' in k and not k.startswith('.'))
        self.CONNECT_POSTFIX_MAP = collections.OrderedDict((k, v) for k, v in self.CONFIG.items('hosts') if ':' in k and k.startswith('.'))
        self.CONNECT_POSTFIX_ENDSWITH = tuple(self.CONNECT_POSTFIX_MAP)

        self.METHOD_REMATCH_MAP = collections.OrderedDict((re.compile(k).match, v) for k, v in self.CONFIG.items('hosts') if '\\' in k)

        self.HTTP_FORCEHTTPS = set(self.CONFIG.get('http', 'forcehttps').split('|'))


        self.PAC_ENABLE = self.CONFIG.getint('pac', 'enable')
        self.PAC_IP = self.CONFIG.get('pac', 'ip')
        self.PAC_PORT = self.CONFIG.getint('pac', 'port')
        self.PAC_FILE = self.CONFIG.get('pac', 'file').lstrip('/')
        self.PAC_GFWLIST = self.CONFIG.get('pac', 'gfwlist')
        self.PAC_ADBLOCK = self.CONFIG.get('pac', 'adblock') if self.CONFIG.has_option('pac', 'adblock') else ''
        self.PAC_EXPIRED = self.CONFIG.getint('pac', 'expired')

        self.CONTROL_ENABLE = self.CONFIG.getint('control', 'enable')
        self.CONTROL_IP = self.CONFIG.get('control', 'ip')
        self.CONTROL_PORT = self.CONFIG.getint('control', 'port')


        self.AUTORANGE_HOSTS = self.CONFIG.get('autorange', 'hosts').split('|')
        self.AUTORANGE_HOSTS_MATCH = [re.compile(fnmatch.translate(h)).match for h in self.AUTORANGE_HOSTS]
        self.AUTORANGE_ENDSWITH = tuple(self.CONFIG.get('autorange', 'endswith').split('|'))
        self.AUTORANGE_NOENDSWITH = tuple(self.CONFIG.get('autorange', 'noendswith').split('|'))
        self.AUTORANGE_MAXSIZE = self.CONFIG.getint('autorange', 'maxsize')
        self.AUTORANGE_WAITSIZE = self.CONFIG.getint('autorange', 'waitsize')
        self.AUTORANGE_BUFSIZE = self.CONFIG.getint('autorange', 'bufsize')
        self.AUTORANGE_THREADS = self.CONFIG.getint('autorange', 'threads')

        self.FETCHMAX_LOCAL = 3


        self.LOVE_ENABLE = self.CONFIG.getint('love', 'enable')
        self.LOVE_TIP = self.CONFIG.get('love', 'tip').encode('utf8').decode('unicode-escape').split('|')

        self.pac_url = 'http://%s:%d/%s\n' % (self.PAC_IP, self.PAC_PORT, self.PAC_FILE)

    def info(self):
        info = ''
        info += '------------------------------------------------------\n'
        info += 'GoAgent Version    : %s (python/%s )\n' % (self.__version__, sys.version[:5])
        info += 'Listen Address     : %s:%d\n' % (self.LISTEN_IP, self.LISTEN_PORT)
        if self.CONTROL_ENABLE:
            info += 'Control Address    : %s:%d\n' % (self.CONTROL_IP, self.CONTROL_PORT)
        info += 'Debug INFO         : %s\n' % self.LISTEN_DEBUGINFO if self.LISTEN_DEBUGINFO else ''
        info += 'GAE APPID          : %s\n' % '|'.join(self.GAE_APPIDS)
        if self.PAC_ENABLE:
            info += 'Pac Server         : http://%s:%d/%s\n' % (self.PAC_IP, self.PAC_PORT, self.PAC_FILE)
            info += 'Pac File           : file://%s\n' % os.path.join(os.path.dirname(os.path.abspath(__file__)), self.PAC_FILE).replace('\\', '/')
        info += '------------------------------------------------------\n'
        return info

common = Common()
#!/usr/bin/python

'''Switch Vlan Module for a BESS based switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

from pyroute2 import IPRoute
from pyroute2.config import AF_BRIDGE

NUD_REACHABLE = 2

class FDB(object):
    '''A python representation of the linux bridge forwarding
       database. By default reads from sysfs and expects a linux
       bridge instance. Read methods can be overriden to support
       other backends.'''

    def __init__(self):
        self._ipr = IPRoute()
        self._ipr.bind()

    @staticmethod
    def _parse(mess):
        '''Parse a Bridge Netlink message'''
        bridge = None
        mac = None
        port = mess['ifindex']
        for (name, value) in mess["attrs"]:
            if name == 'NDA_LLADDR':
                mac = value
            elif name == 'NDA_MASTER':
                bridge = value
        if bridge is None or mac is None or port is None:
            raise KeyError
        return (mess["event"], bridge, {"addr":mac, "port":port})

    def initial_read(self):
        '''Read the FDB state at start'''
        execute = []
        for mess in self._ipr.get_neighbours(
                AF_BRIDGE, match=lambda x: x['state'] == NUD_REACHABLE):
            try:
                execute.append(self._parse(mess))
            except KeyError:
                pass
        return execute

    def iteration(self):
        '''Handle Netlink messages'''
        execute = []
        messages = self._ipr.get()
        for mess in messages:
            try:
                if mess["family"] == AF_BRIDGE and mess["state"] == NUD_REACHABLE:
                    execute.append(self._parse(mess))
            except KeyError:
                pass
        return execute

    def lookup(self, name):
        '''Lookup the index of an interface'''
        return self._ipr.link_lookup(ifname=name)[0]

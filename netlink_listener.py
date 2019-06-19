#!/usr/bin/python

'''Netlink Listener for a Bess switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import logging
import time
from pyroute2 import IPRoute
from pyroute2.config import AF_BRIDGE

NUD_REACHABLE = 0x2
NUD_STALE = 0x4
NUD_PERMANENT = 0x80
NUD_MASK = (NUD_REACHABLE | NUD_STALE)

DEFAULT_AGE = 300


class NetlinkFeed(object):
    def __init__(self):
        self._ipr = IPRoute()
        self._ipr.bind()
        self._index_to_name = {}
        self.rebuild_index()

    def rebuild_index(self):
        '''Rebuild index to name hash'''
        self._index_to_name = {}
        for iface in self._ipr.get_links('all'):
            index = iface["index"]
            for (attr, value) in iface["attrs"]:
                if attr == 'IFLA_IFNAME':
                    self._index_to_name[index] = value
                    break
        

    def _parse(self, mess):
        '''Parse a Bridge Netlink message'''
        if mess["state"] & NUD_PERMANENT:
            # we do not deal with any permanent entries for now
            raise KeyError
        bridge = None
        mac = None
        port = mess['ifindex']
        for (name, value) in mess["attrs"]:
            if name == 'NDA_LLADDR':
                mac = value
            elif name == 'NDA_MASTER':
                bridge = value
        if bridge is None or mac is None or port is None:
            logging.error("Failed to parse message %s", mess)
            raise KeyError
        return {"type":mess["event"], "bridge":bridge, "mac":mac, "port":port}

    def initial_read(self):
        '''Read the FDB state at start'''
        execute = []
        for mess in self._ipr.get_neighbours(
                AF_BRIDGE, match=lambda x: x['state'] & NUD_REACHABLE):
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
                if mess["family"] == AF_BRIDGE and (mess["state"] & NUD_MASK):
                    execute.append(self._parse(mess))
            except KeyError:
                pass
        return execute

    def lookup_by_name(self, name):
        '''Lookup the index of an interface'''
        return self._ipr.link_lookup(ifname=name)[0]

    def lookup_by_index(self, index):
        '''Lookup the index of an interface'''
        return self._index_to_name[index]

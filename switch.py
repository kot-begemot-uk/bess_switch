#!/usr/bin/python

'''Top Level switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import logging
import json
from argparse import ArgumentParser
from select import epoll
from pybess.bess import BESS
from fdb import FDB
from netlink_listener import NetlinkFeed
from vlan import Vlan

class Switch(object):
    '''A python representation of a BESS vlan'''

    def __init__(self, bess):
        self._vlans = {}
        self._ifindexes = {}
        self._initialized = False
        self._fdb = FDB()
        self._epfd = epoll()
        self._feeds = {}
        self._nl = NetlinkFeed()
        self._feeds[self._nl.fileno()] = self._nl
        self._bess = bess

    def deserialize(self, config):
        '''Digest data read from JSON'''
        for vlan_config in config["vlans"]:
            vlan = Vlan(self._bess, vlan_config)
            self._vlans[vlan.ifname] = vlan

    def initialize(self):
        '''Create underlying VLAN and BESS port'''
        try:
            self._initialized = True
            for vlan in self._vlans.values():
                vlan.initialize()
                self._ifindexes[self._nl.lookup_by_name(vlan.ifname)] = vlan
                for port in vlan.ports:
                    self._ifindexes[self._nl.lookup_by_name(port.ifname)] = port
                    self._feeds[port.snoopfeed.fileno()] = port.snoopfeed
        except IOError:
            self._initialized = False

    def _by_index(self, number):
        '''Lookup ifindex from name'''
        return self._ifindexes[number]

    def main_loop(self):
        '''Main processing loop'''
        for feed in self._feeds.values():
            for mess in feed.initial_read():
                logging.debug("Initial %s", mess)
                if mess["type"] == "RTM_NEWNEIGH":
                    self._fdb.learn(
                        mess["mac"], self._ifindexes[mess["bridge"]], self._ifindexes[mess["port"]])
            feed.setblocking(0)
            logging.error("registering for epoll: %d", feed.fileno())
            self._epfd.register(feed.fileno())
        while True:
            events = self._epfd.poll(0.5)
            for (file_d, mask) in events:
                feed = self._feeds[file_d]
                try:
                    for mess in feed.iteration():
                        try:
                            if mess.get("bridge", None) is None:
                                mess["bridge"] = self._by_index(mess["bridge_name"])
                            if mess.get("port", None) is None:
                                mess["port"] = self._by_index(mess["port_name"])
                            if mess["type"] == "RTM_NEWNEIGH":
                                self._fdb.learn(mess["mac"], mess["bridge"], mess["port"])
                            elif mess["type"] == "RTM_DELNEIGH":
                                self._fdb.expire(mess["mac"], mess["bridge"])
                            elif mess["type"] == "MCAST_JOIN":
                                self._fdb.add_mcast(mess["mac"], mess["bridge"], mess["port"])
                            elif mess["type"] == "MCAST_LEAVE":
                                self._fdb.del_mcast(mess["mac"], mess["bridge"], mess["port"])
                            else:
                                logging.error("Unrecognized fdb message: %s", mess)
                        except KeyError:
                            logging.error("Message parsing failure: %s", mess)
                except TypeError:
                    pass

def main():
    '''Main Subroutine'''
    aparser = ArgumentParser(description=main.__doc__)
    aparser.add_argument(
        '--config',
        help='json formatted file containing switch config',
        type=str, required=True)
    aparser.add_argument('--verbose', help='verbosity level', type=int)
    args = vars(aparser.parse_args())
    if args.get('verbose') is not None:
        logging.getLogger().setLevel(logging.DEBUG)
    config = json.load(open(args.get('config'), "r"))
    logging.debug("Config %s", config)
    bess = BESS()
    logging.debug("Connecting to bess")
    bess.connect()
    logging.debug("Reset Pipeline")
    bess.reset_all()
    logging.debug("Reset Ports")
    bess.reset_ports()
    logging.debug("Create Switch")
    switch = Switch(bess)
    logging.debug("Process Config")
    switch.deserialize(config)
    logging.debug("Initialize")
    switch.initialize()
    logging.debug("Fire at will")
    bess.resume_all()
    try:
        switch.main_loop()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

#!/usr/bin/python

'''Top Level switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import logging
import json
from argparse import ArgumentParser
from pybess.bess import BESS
from netlink_listener import FDB
from vlan import Vlan

class Switch(object):
    '''A python representation of a BESS vlan'''

    def __init__(self, bess):
        self._bess = bess
        self._vlans = []
        self._ifindexes = {}
        self._initialized = False
        self._fdb = FDB()

    def deserialize(self, config):
        '''Digest data read from JSON'''
        for vlan_config in config["vlans"]:
            vlan = Vlan(self._bess, vlan_config)
            self._vlans.append(vlan)

    def initialize(self):
        '''Create underlying VLAN and BESS port'''
        try:
            self._initialized = True
            for vlan in self._vlans:
                vlan.initialize()
                self._ifindexes[self._fdb.lookup(vlan.ifname())] = vlan
                for port in vlan.ports():
                    self._ifindexes[self._fdb.lookup(port.port_name)] = port
        except IOError:
            self._initialized = False

    def main_loop(self):
        '''Netlink listener loop'''
        messages = self._fdb.initial_read()
        while True:
            req_queue = {}
            for (event, vindex, data) in messages:
                target_vlan = self._ifindexes[vindex]
                try:
                    req_queue[target_vlan].append((event, self._ifindexes[data['port']], data['addr']))
                except KeyError:
                    req_queue[target_vlan] = [(event, self._ifindexes[data['port']], data['addr'])]
            for (vlan, changes) in  req_queue.items():
                vlan.update_fdb(changes)

            messages = self._fdb.iteration()

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

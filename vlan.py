#!/usr/bin/python

'''Switch Vlan Module for a BESS based switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import logging
import subprocess
from switchport import SwitchPort

class Vlan(object):
    '''A python representation of a BESS vlan'''

    def __init__(self, bess, config=None):
        self.vlan_no = None
        self._bess = bess
        self._ports = []
        self._replicators = {} # hashed by MAC address
        self._initialized = False
        if config is not None:
            self.deserialize(config)
        self._fdb = None

    def ifname(self):
        '''Build default interface name'''
        return "bvlan{}".format(self.vlan_no)

    def ports(self):
        '''Accessor for port list'''
        return self._ports

    def serialize(self):
        '''Prep the vlan for json store'''
        ser_ports = []
        for port in self._ports:
            ser_ports.append(port.serialize())
        return {"vlan":self.vlan_no, "ports":ser_ports}

    def deserialize(self, ser_object):
        '''Digest data read from JSON'''
        self.vlan_no = ser_object["vlan_id"]
        self._ports = []
        for serport in ser_object["ports"]:
            port = SwitchPort(self._bess, self, serport)
            self._ports.append(port)

    def _create(self):
        '''Create the underlying Linux Bridge'''
        logging.debug("Creatig Bridge %s", self.ifname())
        subprocess.call(["/sbin/brctl", "addbr", self.ifname()])

    def _add_if(self, ifname):
        '''Create the underlying Linux Bridge'''
        logging.debug("Adding interface %s to Bridge %s", ifname, self.ifname())
        subprocess.call(["/sbin/brctl", "addif", self.ifname(), ifname])

    def _link(self, status):
        '''Up/Down Link'''
        logging.debug("Linkf for VLAN %s %s", self.vlan_no, status)
        subprocess.call(["/sbin/ip", "link", "set", self.ifname(), status])

    def initialize(self):
        '''Create underlying VLAN and BESS port'''
        self._initialized = True
        logging.debug("Init VLAN %s", self.vlan_no)
        self._create()
        for port in self._ports:
            port.initialize()
            self._add_if(port.port_name)
        self._link("up")

    def update_fdb(self, changes):
        '''Synchronize VLAN Forwarding State'''
        for port in self._ports:
            port.update_fdb(changes)

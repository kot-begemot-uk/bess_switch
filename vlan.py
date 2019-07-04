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
        self._p_by_name = {}
        self._initialized = False
        # list of "port sets" which we use for group mappings
        if config is not None:
            self.deserialize(config)

    @property
    def ifname(self):
        '''Build default interface name'''
        return "bvlan{}".format(self.vlan_no)

    @property
    def ports(self):
        '''Accessor for port list'''
        return self._p_by_name.values()

    @property
    def port_names(self):
        '''Accessor for port list'''
        return self._p_by_name.keys()

    def port_by_name(self, name):
        '''Return port by its name'''
        return self._p_by_name[name]

    def serialize(self):
        '''Prep the vlan for json store'''
        serports = []
        for port in self.ports:
            serports.append(port.serialize())
        return {"vlan":self.vlan_no, "ports":serports}

    def deserialize(self, ser_object):
        '''Digest data read from JSON'''
        self.vlan_no = ser_object["vlan_id"]
        self._p_by_name = {}
        for serport in ser_object["ports"]:
            port = SwitchPort(self._bess, self, serport)
            self._p_by_name[port.ifname] = port

    def _create(self):
        '''Create the underlying Linux Bridge'''
        logging.debug("Creatig Bridge %s", self.ifname)
        subprocess.call(["/sbin/brctl", "addbr", self.ifname])

    def _add_if(self, ifname):
        '''Create the underlying Linux Bridge'''
        logging.debug("Adding interface %s to Bridge %s", ifname, self.ifname)
        subprocess.call(["/sbin/brctl", "addif", self.ifname, ifname])

    def _link(self, status):
        '''Up/Down Link'''
        logging.debug("Linkf for VLAN %s %s", self.vlan_no, status)
        subprocess.call(["/sbin/ip", "link", "set", self.ifname, status])

    def initialize(self):
        '''Create underlying VLAN and BESS port'''
        self._initialized = True
        logging.debug("Init VLAN %s", self.vlan_no)
        self._create()
        port_names = []
        for port in self.ports:
            port_names.append(port.ifname)
        for port in self.ports:
            port.initialize()
            self._add_if(port.ifname)
        # add default replicator for broadcast/multicast to all
        self._link("up")

    def refresh(self, entry):
        '''Update an entry (do nothing for now)'''
        pass

    def delete(self, entry):
        '''Delete an entry'''
        for port in self.ports:
            port.delete(entry)

    def replace(self, entry):
        '''Replace an entry'''
        for port in self.ports:
            port.replace(entry)

    def add(self, entry):
        '''Add an entry'''
        for port in self.ports:
            port.add(entry)

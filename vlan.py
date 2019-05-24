#!/usr/bin/python

'''Switch Vlan Module for a BESS based switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import logging
import subprocess
import os
import struct
from switchport import SwitchPort

class FDB(object):
    '''A python representation of the linux bridge forwarding
       database. By default reads from sysfs and expects a linux
       bridge instance. Read methods can be overriden to support
       other backends.'''

    def __init__(self, bridge):
        self._bridge = bridge
        self._macs = {}
        self._ifaces = {}
        self.refresh()

    def _findportno(self, iface):
        '''Get the ifindex of an interface'''
        with open("/sys/class/net/{bridge}/brif/{iface}/port_no".format(
            bridge=self._bridge, iface=iface)) as ifile:
            return int(ifile.read(), 0)

    def refresh(self):
        '''Refresh the FDB state'''
        self._macs = {}
        self._ifaces = {}
        for port in os.listdir("/sys/class/net/{}/brif".format(self._bridge)):
            self._ifaces[self._findportno(port)] = port
        with open("/sys/class/net/{}/brforward".format(self._bridge)) as fdb:
            data = fdb.read(16)
            while data is not None and data:
                mac0, mac1, mac2, mac3, mac4, mac5, portno, islocal, aging = \
                    struct.unpack("BBBBBBBBL", data)
                self._macs["{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(
                    mac0, mac1, mac2, mac3, mac4, mac5
                    )] = {"ifname": self._ifaces[portno], "age":aging, "islocal":(islocal > 0)}
                data = fdb.read(16)

    def lookup(self, mac, refresh=True):
        '''Lookup a Mac'''
        if refresh:
            self.refresh()
        return self._macs.get(mac)

    def get_fdb(self):
        '''Return curent fdb'''
        return self._macs

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

    def _ifname(self):
        '''Build default interface name'''
        return "bvlan{}".format(self.vlan_no)

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
        logging.debug("Creatig Bridge %s", self._ifname())
        subprocess.call(["/sbin/brctl", "addbr", self._ifname()])

    def _add_if(self, ifname):
        '''Create the underlying Linux Bridge'''
        logging.debug("Adding interface %s to Bridge %s", ifname, self._ifname())
        subprocess.call(["/sbin/brctl", "addif", self._ifname(), ifname])

    def _link(self, status):
        '''Up/Down Link'''
        logging.debug("Linkf for VLAN %s %s", self.vlan_no, status)
        subprocess.call(["/sbin/ip", "link", "set", self._ifname(), status])

    def initialize(self):
        '''Create underlying VLAN and BESS port'''
        self._initialized = True
        logging.debug("Init VLAN %s", self.vlan_no)
        self._create()
        for port in self._ports:
            port.initialize()
            self._add_if(port.port_name)
        self._link("up")
        self._fdb = FDB(self._ifname())

    def update_fdb(self):
        '''Synchronize VLAN Forwarding State'''
        self._fdb.refresh()
        for port in self._ports:
            port.update_fdb(self._fdb.get_fdb())

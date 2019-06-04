#!/usr/bin/python

'''Switch Port Module for a BESS based switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see LICENSE in source directory

import logging
import re

PORT_RE = re.compile(r"bv(\d+)p(\d+)")

class SwitchPort(object):
    '''A python representation of a BESS switch port'''

    # I will have as many as I need thank ya
    # pylint: disable=too-many-instance-attributes
    def __init__(self, bess, vlan, args=None):
        self._bess = bess
        self._vlan = vlan
        self._args = args
        logging.debug("Port Args are %s", args)
        self._phys_port = None
        self._logical_port = None
        self._replicators = []
        self._initialized = False
        self._active_fdb = {}
        self._pg_map = {}

    @property
    def _pci_id(self):
        return self._args.get("pci")

    @property
    def _inc_q(self):
        try:
            return self._args["num_inc_q"]
        except KeyError:
            return 1

    @property
    def _out_q(self):
        try:
            return self._args["num_out_q"]
        except KeyError:
            return 1

    @property
    def _cpu_set(self):
        try:
            return self._args["rxq_cpus"]
        except KeyError:
            return [0]

    @property
    def port_name(self):
        '''Return assigned or build default port name'''
        return "bv{}p{}".format(self._vlan.vlan_no, self._args["port_no"])

    def _hout_port(self, port):
        '''Return the expected out port or None if it is not a BESS port'''
        try:
            out_port = "houtbv{}p{}".format(self._vlan.vlan_no, PORT_RE.match(port).group(2))
            if out_port == "hout{}".format(self.port_name):
                return None # do not loop traffic
            return out_port
        except TypeError:
            logging.debug("No matching gate for port %s", port)
            return None

    def _add_portgate(self, port):
        '''Add a new gate for the new port'''
        candidate = self._hout_port(port)
        if candidate is None:
            return None
        hout_port = self._hout_port(port)
        if hout_port is None:
            return None
        maxgate = max(self._pg_map.values()) + 1
        self._pg_map[port] = maxgate
        logging.debug("Wiring %s to gate %d on port %s", port, maxgate, self.port_name)
        self._bess.connect_modules(
            "f{}".format(self.port_name), hout_port, ogate=maxgate)
        return maxgate

    def _p_to_g(self, port):
        '''Map VLAN port number to forwarding locally significant forwarding gate'''
        if port is None:
            return None
        try:
            return self._pg_map[port]
        except KeyError:
            return self._add_portgate(port)

    def serialize(self):
        '''Prep the port for json store'''
        return self._args

    def deserialize(self, args):
        '''Digest data read from JSON'''
        self._args = args

    def initialize(self):
        '''Create underlying BESS port'''
        self._initialized = True
        # we are using only PCI Ids for now.
        if self._pci_id is not None:
            logging.debug("Phys Port for %s", self.port_name)
            self._phys_port = self._bess.create_port(
                "PMDPort", "h{}".format(self.port_name),
                {"pci":self._pci_id, "num_inc_q":self._inc_q, "num_out_q":self._out_q})
        if self.port_name is not None:
            logging.debug("Logical Port for %s", self.port_name)
            self._logical_port = self._bess.create_port(
                "VPort", "v{}".format(self.port_name),
                {"ifname":self.port_name, "rxq_cpus":self._cpu_set})

        if self._phys_port is not None:
            logging.debug("Pipeline for %s", self.port_name)
            p_in = self._bess.create_module(
                "PortInc", "hin{}".format(self.port_name), {"port": "h{}".format(self.port_name)})
            p_out = self._bess.create_module(
                "PortOut", "hout{}".format(self.port_name), {"port": "h{}".format(self.port_name)})
            v_in = self._bess.create_module(
                "PortInc", "vin{}".format(self.port_name), {"port": "v{}".format(self.port_name)})
            v_out = self._bess.create_module(
                "PortOut", "vout{}".format(self.port_name), {"port": "v{}".format(self.port_name)})
            forwarder = self._bess.create_module(
                "L2Forward", "f{}".format(self.port_name), {})

            self._bess.run_module_command(
                forwarder.name,
                "set_default_gate",
                "L2ForwardCommandSetDefaultGateArg",
                {"gate":0})
            self._pg_map[-1] = 0 # default gate
            self._bess.connect_modules(p_in.name, forwarder.name)
            self._bess.connect_modules(forwarder.name, v_out.name, ogate=0)
            self._bess.connect_modules(v_in.name, p_out.name)


    def _del_rules(self, mac_list):
        '''Del MAC-GATE Rules'''
        if mac_list:
            self._bess.run_module_command(
                "f{}".format(self.port_name),
                "delete",
                "L2ForwardCommandDeleteArg",
                {"addrs":mac_list})

    def _add_rules(self, entries):
        '''Add MAC-GATE Rules'''
        if entries:
            self._bess.run_module_command(
                "f{}".format(self.port_name),
                "add",
                "L2ForwardCommandAddArg",
                {"entries":entries})

    def update_fdb(self, changes):
        '''Apply Forwarding Database rules'''
        to_del = []
        to_add = []

        for (oper, port, mac) in changes:
            if oper == 'RTM_NEWNEIGH' and port != self:
                p_g = self._p_to_g(port.port_name)
                if p_g is not None:
                    to_add.append({"addr":mac, "gate":p_g})
            if oper == 'RTM_DELNEIGH':
                p_g = self._p_to_g(port.port_name)
                if p_g is not None:
                    to_del.append(mac)
        try:
            if to_del:
                logging.debug("Deleting on %s %s", self.port_name, to_del)
                self._del_rules(to_del)
        except:
            logging.error("Bess rejected deletion, MAC not in table")
                
            
        try:
            if to_add:
                logging.debug("Adding on %s %s", self.port_name, to_add)
                self._add_rules(to_add)
        except:
            logging.error("Bess rejected addition, MAC already in table")

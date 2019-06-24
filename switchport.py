#!/usr/bin/python

'''Switch Port Module for a BESS based switch'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see LICENSE in source directory

import logging
import re
import copy

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
        self._replicators = {}
        self._initialized = False
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
    def ifname(self):
        '''Return assigned or build default port name'''
        return "bv{}p{}".format(self._vlan.vlan_no, self._args["port_no"])


    def replicator(self, port_list_arg):
        '''Add a list of replicators'''
        port_list = copy.copy(port_list_arg)
        try:
            port_list.remove(self.ifname)
        except ValueError:
            pass
        if len(port_list) == 0:
            return
        logging.debug("Stargate SG1 on %s %s", self.ifname, port_list)
        hash_key = "-".join(sorted(port_list))
        try:
            if self._replicators[hash_key]:
                return "rep{}-{}".format(self.ifname, hash_key)
        except KeyError:
            pass
        logging.debug("Replicate  %s %s", self.ifname, port_list)
        self._bess.create_module(
            "Replicate", "rep{}-{}".format(self.ifname, hash_key), {"gates":[]})
        self._replicators[hash_key] = True
        self._bess.resume_all()

        # run all args via the gate mapper and reuse the gate mapping
        logging.debug("Dry run for  %s %s", self.ifname, port_list)
        for port_name in port_list:
            self._p_to_g(port_name)
        gate_list = []
        # wire all gates using the same gate mapping as the L2Forwarder
        for port_name in port_list:
            try:
                hout = self._hout_port(port_name)
                if hout is not None:
                    self._bess.connect_modules(
                        "rep{}-{}".format(
                            self.ifname, hash_key), hout, ogate=self._pg_map[port_name])
                    gate_list.append(self._pg_map[port_name])
            except KeyError:
                pass
        # Set the gates as an arg
        logging.debug("Gate address  %s %s", self.ifname, port_list)
        self._bess.run_module_command(
            "rep{}-{}".format(self.ifname, hash_key),
            "set_gates",
            "ReplicateCommandSetGatesArg",
            {"gates":gate_list})
        return "rep{}-{}".format(self.ifname, hash_key)

    def _hout_port(self, port):
        '''Return the expected out port or None if it is not a BESS port'''
        try:
            out_port = "houtbv{}p{}".format(self._vlan.vlan_no, PORT_RE.match(port).group(2))
            if out_port == "hout{}".format(self.ifname):
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
        logging.debug("Wiring %s to gate %d on port %s", port, maxgate, self.ifname)
        self._bess.connect_modules(
            "f{}".format(self.ifname), hout_port, ogate=maxgate)
        return maxgate

    def _p_to_g(self, port):
        '''Map VLAN port number to forwarding locally significant forwarding gate'''
        if port is None:
            return None
        try:
            return self._pg_map[port]
        except KeyError:
            return self._add_portgate(port)

    def _add_mcastgate(self, replicator):
        '''Add a new gate for the multicast replicator'''
        maxgate = max(self._pg_map.values()) + 1
        self._pg_map[replicator] = maxgate
        logging.debug("Wiring %s to gate %d on port %s", replicator, maxgate, self.ifname)
        self._bess.connect_modules(
            "f{}".format(self.ifname), replicator, ogate=maxgate)
        return maxgate


    def _m_to_g(self, ports_arg):
        '''Map multicast group to forwarding locally significant forwarding gate'''
        ports = copy.copy(ports_arg)
        if ports is None:
            return None
        try:
            ports.remove(self.ifname)
        except ValueError:
            pass

        if len(ports) == 0:
            return

        logging.debug("Mapping multicast gate on %s for %s", self.ifname, ports)
            
        try:
            return self._pg_map[self.replicator(ports)]
        except KeyError:
            return self._add_mcastgate(self.replicator(ports))

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
            logging.debug("Phys Port for %s", self.ifname)
            self._phys_port = self._bess.create_port(
                "PMDPort", "h{}".format(self.ifname),
                {"pci":self._pci_id, "num_inc_q":self._inc_q, "num_out_q":self._out_q})
        if self.ifname is not None:
            logging.debug("Logical Port for %s", self.ifname)
            self._logical_port = self._bess.create_port(
                "VPort", "v{}".format(self.ifname),
                {"ifname":self.ifname, "rxq_cpus":self._cpu_set})

        if self._phys_port is not None:
            logging.debug("Pipeline for %s", self.ifname)
            p_in = self._bess.create_module(
                "PortInc", "hin{}".format(self.ifname), {"port": "h{}".format(self.ifname)})
            p_out = self._bess.create_module(
                "PortOut", "hout{}".format(self.ifname), {"port": "h{}".format(self.ifname)})
            v_in = self._bess.create_module(
                "PortInc", "vin{}".format(self.ifname), {"port": "v{}".format(self.ifname)})
            v_out = self._bess.create_module(
                "PortOut", "vout{}".format(self.ifname), {"port": "v{}".format(self.ifname)})
            forwarder = self._bess.create_module(
                "L2Forward", "f{}".format(self.ifname), {"source_check": True})

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
                "f{}".format(self.ifname),
                "delete",
                "L2ForwardCommandDeleteArg",
                {"addrs":mac_list})

    def _add_rules(self, entries):
        '''Add MAC-GATE Rules'''
        if entries:
            self._bess.run_module_command(
                "f{}".format(self.ifname),
                "add",
                "L2ForwardCommandAddArg",
                {"entries":entries})

    def refresh(self, change):
        '''As we do not have counters yet, a refresh is a pass'''
        pass


    def add(self, change):
        '''Add a MAC route from fdb, fdb now splits them into
           single entry commands so we do not do bulking any more'''
        if change.source == self:
            return
        to_add = []
        p_g = None
        if change.is_broadcast:
            logging.debug("Add requested for %s %s", self.ifname, change.ports)
            p_g = self._m_to_g(change.ports)
        else:
            p_g = self._p_to_g(change.source.ifname)
        if p_g is not None:
            to_add.append({"addr":change.mac, "gate":p_g})
        try:
            if to_add:
                logging.debug("Adding on %s %s", self.ifname, to_add)
                self._add_rules(to_add)
        # the exceptions barfed by the grpc stack are anything but "well defined"
        # pylint: disable=bare-except
        except:
            logging.error("Add failed on %s %s", self.ifname, to_add)

    def delete(self, change):
        '''Add a MAC route from fdb, fdb now splits them into
           single entry commands so we do not do bulking any more'''
        # we do not do not skip a deletion request even if the dest
        # port is ourselves. The reason for this is that in case of a
        # port move the new port may be ourselves, the old one is a
        # different port for which we need to delete the routing entry
        to_del = [change.mac]
        try:
            logging.debug("Deleting on %s %s", self.ifname, to_del)
            self._del_rules(to_del)
        # the exceptions barfed by the grpc stack are anything but "well defined"
        # pylint: disable=bare-except
        except:
            logging.error("Delete failed on %s %s", self.ifname, to_del)

    def replace(self, change):
        '''Add a MAC route from fdb, fdb now splits them into
           single entry commands so we do not do bulking any more'''
        self.delete(change)
        self.add(change)

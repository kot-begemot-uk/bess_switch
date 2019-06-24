#!/usr/bin/python

'''Forwarding Database'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import logging
import time

DEFAULT_AGE = 300


class FDBEntry(object):
    '''FDB Entry'''
    def __init__(self, mac, vlan, source, dst_ports=None, age=DEFAULT_AGE):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
        self._mac = mac
        self._source = source
        self._dst_ports = dst_ports
        self._is_broadcast = is_bmcast(mac)
        self._vlan = vlan
        self._age = age
        self.last_seen = 0 # this one needs to be public for testing
        self.refresh()

    @property
    def ports(self):
        '''Port list to direct traffic to.'''
        return self._dst_ports

    @property
    def mac(self):
        '''MAC for this fdb entry'''
        return self._mac

    @property
    def is_broadcast(self):
        '''Is this Broadcast or Multicast'''
        return self._is_broadcast

    @property
    def vlan(self):
        '''vlan for this fdb entry'''
        return self._vlan

    @property
    def source(self):
        '''Source port for this fdb entry'''
        return self._source

    def refresh(self):
        '''Refresh this entry'''
        self.last_seen = time.time()
        self._expiry = self.last_seen + self._age

    def add_port(self, dst_port):
        '''Add a dst port'''
        try:
            self._dst_ports.index(dst_port)
        except ValueError:
            self._dst_ports.append(dst_port)

    def del_port(self, dst_port):
        '''Add a dst port'''
        try:
            self._dst_ports.remove(dst_port)
        except ValueError:
            pass

    

class FDB(object):
    '''A python representation of the linux bridge forwarding
       database. By default reads from sysfs and expects a linux
       bridge instance. Read methods can be overriden to support
       other backends.'''
    def __init__(self):
        self._records = {}

    def get_entry(self, mac, vlan):
        '''Get entry from fdb for this mac - note that a mac can be
           present on any number of vlans, thus you need to hash
           on mac + vlan'''
        return self._records["{}-{}".format(vlan, mac)]

    def add_entry(self, entry):
        '''Add entry from fdb for this mac - note that a mac can be
           present on any number of vlans, thus you need to hash
           on mac + vlan'''
        self._records["{}-{}".format(entry.vlan, entry.mac)] = entry

    def delete_entry(self, entry):
        '''Delete entry from fdb for this mac - note that a mac can be
           present on any number of vlans, thus you need to hash
           on mac + vlan'''
        del self._records["{}-{}".format(entry.vlan, entry.mac)]

    def add_mcast(self, mac, vlan, dest_ports):
        '''Add a Multicast fdb entry'''
        try:
            old = self.get_entry(mac, vlan)
            if len(dest_ports) == 0:
                self.delete_entry(old)
                vlan.delete(old)
                return
            try:
                for port in dest_ports:
                    old.ports.index(port)
                for port in old.ports:
                    dest_ports.index(port)
                old.refresh()
                vlan.refresh(old)
                return
            except ValueError:
                self.delete_entry(old)
                new = FDBEntry(mac, vlan, None, dst_ports=dest_ports)
                self.add_entry(new)
                vlan.replace(old, new)
        except KeyError:
            entry = FDBEntry(mac, vlan, None, dst_ports=dest_ports)
            self.add_entry(entry)
            vlan.add(entry)

    def learn(self, mac, vlan, source_port):
        '''Add or refresh a mac'''
        try:
            old = self.get_entry(mac, vlan)
            if old.source == source_port:
                old.refresh()
                vlan.refresh(old)
            else:
                self.delete_entry(old)
                new = FDBEntry(mac, vlan, source_port)
                self.add_entry(new)
                vlan.replace(old, new)
        except KeyError:
            entry = FDBEntry(mac, vlan, source_port)
            self.add_entry(entry)
            vlan.add(entry)

    def expire(self, mac, vlan):
        '''Delete Mac'''
        try:
            entry = self.get_entry(mac, vlan)
            if entry.vlan is not None:
                vlan.delete(entry)
                self.delete_entry(entry)
        except KeyError:
            logging.error("tried to delete inexistent mac %s on vlan %s", mac, vlan)


def is_bmcast(mac):
    '''Is the mac broadcast or multicast. As a
       side effect, validates and parses the mac'''

    digits = mac.split(":")
    if len(digits) != 6:
        raise ValueError
    for digit in digits:
        hex_form = int(digits[0], 16)
        if hex_form < 0 or hex_form > 0xff:
            raise ValueError
    return (int(digits[0], 16) & 1) == 1

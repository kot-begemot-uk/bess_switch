#!/usr/bin/python


'''IGMP Listener'''

# Copyright (c) 2019 Red Hat Inc
#
# License: GPL2, see COPYING in source directory

import socket
import logging
import scapy.all as scapy
from scapy.layers.l2 import Ether
import pcapy


MAXPACKET = 1500
FILTER = "proto 2"
MAX_COUNT = 128
IGMP_CH_INCLUDE = 3 # equivalent of LEAVE if SRC == 0
IGMP_CH_EXCLUDE = 4 # equivalent of JOIN  if SRC == 0


class IGMPFeed(object):
    '''IGMP Listener'''

    def __init__(self, iface=None):
        self.iface = iface
        self.pcap = pcapy.open_live(iface.encode('ascii'), MAXPACKET, True, 0)
        self.pcap.setfilter(FILTER)
        self.pcap.setnonblock(True)
        scapy.load_contrib('igmpv3')
        scapy.load_contrib('igmp')

    def _parse(self, packet):
        '''Parse IGMP and other packets we track via pcap. Returns a mix of "learn" events which are the same
           as in normal MAC learning and events for IGMP groups'''
        result = []

        igmp = packet.getlayer(IGMPv3mr)
        if igmp is not None:
            try:
                for rec in igmp.fields['records']:
                    for subrec in rec:
                        print "{}".format(subrec.rtype)
                        if subrec.numsrc == 0 and subrec.rtype == IGMP_CH_INCLUDE:
                                result.append({
                                    "type":"leave",
                                    "iface":self.iface,
                                    "mac":convert_to_mac(subrec.maddr),
                                    "group":subrec.maddr,
                                    "src":packet.src})
                        else:
                                result.append({
                                    "type":"join",
                                    "iface":self.iface,
                                    "mac":convert_to_mac(subrec.maddr),
                                    "group":subrec.maddr,
                                    "src":packet.src})
                            
            except TypeError: 
                pass
        return result
    def initial_read(self):
        '''We have no means to read multicast state at start, we can only build it as we go along'''
        return []

    def iteration(self):
        '''Handle PCAP reads'''
        execute = []
        packets = []
        try:
            count = 0
            while count < MAX_COUNT:
                (hdr, data) = self.pcap.next()
                packets.append(Ether(data))
        except TypeError:
            pass
        except socket.timeout:
            pass

        for packet in packets:
            try:
                execute = execute + self._parse(packet)
            except KeyError:
                pass
        return execute

MCAST_OID = "01:00:5e"

def convert_to_mac(ip):
    '''Convert an IP MCAST group address to its corresponding
       mac address'''
    digits = ip.split(".")
    upper = int(digits[1], 16) & 0x7f
    return "{}:{:x}:{:x}:{:x}".format(MCAST_OID, upper, 
        int(digits[2]), int(digits[3]))

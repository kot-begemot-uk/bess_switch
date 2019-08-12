//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package Reader

import "net"
import log "github.com/sirupsen/logrus"
import "time"
import "github.com/google/gopacket"
import "github.com/google/gopacket/layers"

const cutoff = 300

type Reader struct {
    c  net.Conn
    buffer  []byte
    path  string
    macs map[string]int64
    learn chan string
    expires chan string
    mcast chan string
}

func NewReader (pathArg string, learnChan chan string, expiresChan chan string, mcastChan chan string) (*Reader) {
    r := &Reader{
        path: pathArg,
        macs: make(map[string]int64),
        buffer: make([]byte, 2048),
        learn: learnChan,
        expires: expiresChan,
        mcast: mcastChan,
    }
    c, err := net.Dial("unixpacket", r.path)
    r.c = c
    if err != nil {
        log.Fatal("Could Not connect:", err)
    }
    return r
}

// This is written to run as a goroutine in blocking mode.

func (r *Reader) ProcessPacket () (int) {
    var count int
    count, err := r.c.Read(r.buffer)


    // Error reading

    if err != nil {
        return -1
    }

    // Remote side has closed the connection

    if count <= 0 {
        return count
    }

    packet := gopacket.NewPacket(r.buffer, layers.LayerTypeEthernet, gopacket.Default)
    ethLayer := packet.Layer(layers.LayerTypeEthernet)
    eth := ethLayer.(*layers.Ethernet)
    if (eth.SrcMAC[0] & 1) == 0 {
        mac := eth.SrcMAC.String()
        // Unicast 
        _, present := r.macs[mac]
        if present {
            // Refresh MAC
            r.macs[mac] = time.Now().Unix()
        } else {
            select {
                case r.learn <- eth.SrcMAC.String():
                    // We cache the Mac only if we have successfully announced it
                    r.macs[eth.SrcMAC.String()] = time.Now().Unix()
                    log.Debugf("learned mac %s", eth.SrcMAC.String())
                default:
                    log.Errorf("failed to write learned mac to channel")
            }
        }
    } // Multicast, arp, etc snooping go in the ELSE clause here 
    to_delete := make([]string, 0)
    for k, v  := range r.macs {
        if time.Now().Unix() - v > cutoff {
            to_delete = append(to_delete, k)
        }
    }
    for _, k := range to_delete {
        select {
            case r.expires <- k:
                // Same as expiry, we delete it only if announcement is successful
                log.Debugf("expired mac %s", k)
                delete(r.macs, k)
            default:
                log.Errorf("failed to write expired mac to channel")
        }
    }
    return count
}

func (r *Reader) Run() {
    for true {
        if r.ProcessPacket() <= 0 {
            r.learn <- "CLOSE"
            return
        }
    }
}

func (r *Reader) Close () {
    r.c.Close()
}



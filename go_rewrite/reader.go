//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package main

import "os"
import "fmt"
import "net"
import "log"
import "time"
import "github.com/google/gopacket"
import "github.com/google/gopacket/layers"

type reader struct {
    c  net.Conn
    buffer  []byte
    path  string
    macs map[string]int64
}

func newReader (pathArg string) (*reader) {
    r := &reader{
		path: pathArg,
		buffer: make([]byte, 2048),
        macs: make(map[string]int64),
    }
    c, err := net.Dial("unixpacket", r.path)
    r.c = c
    if err != nil {
        log.Fatal("Could Not connect:", err)
    }
    return r
}

func (r *reader) processPacket () (int) {
    var count int
    count, err := r.c.Read(r.buffer)
    packet := gopacket.NewPacket(r.buffer, layers.LayerTypeEthernet, gopacket.Default)
    ethLayer := packet.Layer(layers.LayerTypeEthernet)
    eth := ethLayer.(*layers.Ethernet)
    if old, ok := r.macs[eth.SrcMAC.String()]; ok {
        fmt.Printf("MAC exists: %s %d", eth.SrcMAC, time.Now().Unix() - old)
        r.macs[eth.SrcMAC.String()] = time.Now().Unix()
    } else {
        if (eth.SrcMAC[0] & 1) > 0 { 
            fmt.Printf("Broadcast Mac: %s ", eth.SrcMAC)
        } else {
            fmt.Printf("Add Mac: %s ", eth.SrcMAC)
            r.macs[eth.SrcMAC.String()] = time.Now().Unix()
        }
    }
    if err != nil {
        log.Fatal("Error Reading", err)
    }
    return count
}

func (r *reader) Close () {
    r.c.Close()
}

func main() {
    rd := newReader(os.Args[1])
    for true {
        fmt.Printf("Received: %d bytes", rd.processPacket())
    }
    defer rd.Close()
}

//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package main

import "os"
import "fmt"
import "net"
import "log"
import "github.com/google/gopacket"
import "github.com/google/gopacket/layers"

type reader struct {
    c  net.Conn
    buffer  []byte
    path  string
}

func newReader (pathArg string) (*reader) {
    r := &reader{
		path: pathArg,
		buffer: make([]byte, 2048),
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
    fmt.Printf("MAC is: %s ", eth.SrcMAC)
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

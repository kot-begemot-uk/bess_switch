//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package agent

import "net"
import log "github.com/sirupsen/logrus"
import "time"
import "github.com/google/gopacket"
import "github.com/google/gopacket/layers"

const cutoff = 300

type Reader struct {
    c  net.Conn
    buffer  []byte
    port string
    path  string
    macs map[string]int64
    control chan L2FIBCommand
}

func NewReader (portArg string, pathArg string, controlChan chan L2FIBCommand) (*Reader) {
    r := &Reader{
        port: portArg,
        path: pathArg,
        macs: make(map[string]int64),
        buffer: make([]byte, 2048),
        control: controlChan,
    }
    c, err := net.Dial("unixpacket", r.path)
    r.c = c
    if err != nil {
        log.Fatal("Could Not connect:", err)
    }
    return r
}

func (r *Reader) GetControl () (chan L2FIBCommand) {
    return r.control
}

func (r *Reader) GetPort () (string) {
    return r.port
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
            command := L2FIBCommand{
                command: "LEARN",
                MAC: eth.SrcMAC.String(),
                permanent: false,
                setage:  time.Now().Unix(),
                port: r.port,
            }
            select {
                case r.control <- command:
                    // We cache the Mac only if we have successfully announced it
                    r.macs[eth.SrcMAC.String()] = command.setage
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
        command := L2FIBCommand{
            command: "EXPIRE",
            MAC: k,
            permanent: false,
            setage:  0,
            port: r.port,
        }
        select {
            case r.control <- command:
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
            command := L2FIBCommand{
                command: "CLOSE",
                MAC: "",
                permanent: false,
                setage:  0,
                port: r.port,
            }
            r.control <- command 
            return
        }
    }
}

func (r *Reader) Close () {
    r.c.Close()
}



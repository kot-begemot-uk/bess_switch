//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package agent

import "reflect"
import "os"
import "fmt"

const (
    BASEDIR = "/var/run/nimbess"
    SOCKETNAME = "/var/run/nimbess/%s"
)

type L2FIBEntry struct {
    permanent bool
    age int64
    port string
}

type L2FIBCommand struct {
    command string
    MAC string
    permanent bool
    setage int64
    port string
}

type L2FIB struct {
    id string // Identifier
    // Notifier from agent
    control chan L2FIBCommand
    // Notifier channels from readers
    ports []string
    agent *NimbessAgent
    fib map[string]L2FIBEntry
    rds []*Reader
}

func NewFIB(fibNAME string, nimbess *NimbessAgent) (*L2FIB) {
    _ = os.Mkdir(BASEDIR, os.ModePerm) // ignore return
    f := &L2FIB {
        id: fibNAME,
        control: make(chan L2FIBCommand),
        ports: make([]string, 0),
        agent: nimbess,
        fib: make(map[string]L2FIBEntry),
        rds: make([]*Reader, 0),
    }
    return f
}

func recoverL2FIBCommand(val reflect.Value) (*L2FIBCommand) {
    return &L2FIBCommand  {
        command: val.Field(0).String(),
        MAC: val.Field(1).String(),
        permanent: val.Field(2).Bool(),
        setage: val.Field(3).Int(),
        port: val.Field(4).String(),
    }
}

func (f *L2FIB) GetControl() (chan L2FIBCommand){
    return f.control
}

func (f *L2FIB) AddPort(name string) {
    control := make(chan L2FIBCommand)
    rd := NewReader(name, fmt.Sprintf(SOCKETNAME, name), control)
    f.rds = append(f.rds, rd)
    go rd.Run()
}

func (f *L2FIB) Iteration() (bool) {
    size := len(f.rds)
    if size == 0 {
        return true
    }
    cases := make([]reflect.SelectCase, size + 1)
    // Join all 
    for i, reader := range f.rds {
        cases[i] = reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(reader.GetControl())}
    }
    cases[size] = reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(f.control)}
    // Make sure the pipelines are available and in a consistent state
    f.agent.Mu.Lock()
    defer f.agent.Mu.Unlock()

    i, value, _ := reflect.Select(cases)
    fibRequest := recoverL2FIBCommand(value)

    if fibRequest.command == "LEARN" {
        // Learned
        f.fib[fibRequest.MAC] = L2FIBEntry {
            permanent: false,
            age:fibRequest.setage,
            port:fibRequest.port,
        }
        for key, pipeline := range f.agent.Pipelines {
            if key != fibRequest.port {
                // no Routing for self
                f.agent.AddL2FIBEntry(fibRequest.MAC, pipeline, fibRequest.port)
            }
        }
    }
    if  fibRequest.command == "EXPIRE" {
        delete(f.fib, fibRequest.MAC)
        for _, pipeline := range f.agent.Pipelines {
            f.agent.DelL2FIBEntry(fibRequest.MAC, pipeline)
        }
    }
    if fibRequest.command == "ADD" {
        f.fib[fibRequest.MAC] = L2FIBEntry {
            permanent: true,
            age:0,
            port:fibRequest.port,
        }
        for key, pipeline := range f.agent.Pipelines {
            if key != f.ports[i] {
                f.agent.AddL2FIBEntry(fibRequest.MAC, pipeline, fibRequest.port)
            }
        }
    }
    if fibRequest.command == "ADDPORT" {
        f.AddPort()
    }
    if fibRequest.command == "CLOSE" {
        // This happens when remote end closes the socket and the right
        // way of doing this cleanly is to close the monitoring port via
        // bess. There is no way to do it from the agent side without
        // changing the threading model and/or IO model
        f.DelPortByName(fibRequest.port)
    }
    return true //Deal with control later
}

func (f *L2FIB) Run() {
    for f.Iteration(fibRequest.MAC) {
    }
}

func (f *L2FIB) delPort(i int) {
    if (i < 0) {
        return
    }
    rd := f.rds[i]
    _ = copy(f.rds[i:], f.rds[i + 1:])
    f.rds = f.rds[:len(f.rds) - 1]
    rd.Close()
}

func (f *L2FIB) DelPortByName(name string) {
    // This is invoked out of Iteration which already holds the mutex
    for index, reader := range f.rds {
        if name == reader.GetPort() {
            f.delPort(index)
            return
        }
    }
}


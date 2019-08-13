//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package pipeline

import "fmt"

//import log "github.com/sirupsen/logrus"



type MockPipeline struct {
    name string
    gateMap map[string]int
    mockFIB map[string]int
}

func NewMockPipeline (mockName string) (*MockPipeline) {
    m := &MockPipeline{
        name: mockName,
        gateMap: make(map[string]int),
        mockFIB: make(map[string]int),
    }
    return m
}

func (m *MockPipeline) GetName() (string) {
    return m.name
}
func (m *MockPipeline) GetMonitorName() (string) {
    return m.name // should return the unix domain socket path
}

// This is written to run as a goroutine in blocking mode.

func (m *MockPipeline) AddFIBEntry (mac string, destPort string) (int) {
    fmt.Println("Adding ", mac, " from ", m.GetName(), " to ", destPort)
    target, ok := m.mockFIB[mac]
    if ok {
        return target
    }
    target, ok = m.gateMap[destPort]
    if !ok {
        target = m.addDestPort(destPort)
    }
    m.mockFIB[mac] = target
    // Replace the mock with a call to program FIB
    fmt.Println("Target gate", target)
    return target
}

func (m *MockPipeline) DelFIBEntry (mac string) (int) {
    // Replace the mock with a call to program FIB
    fmt.Println("Deleting MAC ", mac)
    delete(m.mockFIB, mac)
    return 0
}

func (m *MockPipeline) addDestPort(name string) (int) {
    max := 0
    for _, v := range m.gateMap {
        if v > max {
            max = v
        }
    }
    m.gateMap[name] = max + 1
    // mock call add gate mapping for gate no max + 1 to name
    return max + 1
}

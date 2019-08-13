//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package fib

import "reflect"
import "reader"
import "pipeline"

type FIB struct {
    name string // Identifier
    // Notifier channels from readers
    learn []chan string
    expire []chan string
    mcast []chan string
    // Readers
    rds []*reader.Reader
    pipelines []*pipeline.MockPipeline
}

func NewFIB(fibNAME string) (*FIB) {
    f := &FIB {
        name: fibNAME,
        learn: make([]chan string, 0),
        expire: make([]chan string, 0),
        mcast: make([]chan string, 0),
        rds:  make([]*reader.Reader, 0),
        pipelines: make([]*pipeline.MockPipeline, 0),
    }
    return f
}

func (f *FIB) AddPort(p *pipeline.MockPipeline) {
    f.pipelines =append(f.pipelines, p)
    learn := make(chan string)
    expire := make(chan string)
    mcast := make(chan string)
    f.learn = append(f.learn, learn)
    f.expire = append(f.expire, expire)
    f.mcast = append(f.mcast, mcast)
    rd := reader.NewReader(p.GetName(), learn, expire, mcast)
    f.rds = append(f.rds, rd)
    go rd.Run()
}

func (f *FIB) delPort(i int) {
    if (i < 0) {
        return
    }
    rd := f.rds[i]
    _ = copy(f.learn[i:], f.learn[i + 1:])
    _ = copy(f.expire[i:], f.expire[i + 1:])
    _ = copy(f.mcast[i:], f.mcast[i + 1:])
    _ = copy(f.rds[i:], f.rds[i + 1:])
    _ = copy(f.pipelines[i:], f.pipelines[i + 1:])
    f.learn = f.learn[:len(f.learn) - 1]
    f.expire = f.expire[:len(f.expire) - 1]
    f.mcast = f.mcast[:len(f.mcast) - 1]
    f.rds = f.rds[:len(f.rds) - 1]
    f.pipelines = f.pipelines[:len(f.pipelines) - 1]
    rd.Close()
}

func (f *FIB) DelPortByName(name string) {
    for index, pipeline := range f.pipelines {
        if pipeline.GetName() == name {
            f.delPort(index)
            return
        }
    }
}

func (f *FIB) Iteration() {
    size := len(f.learn)
    if size == 0 {
        return
    }
    cases := make([]reflect.SelectCase, size * 3)
    // Join all 
    for i, channel := range f.learn {
        cases[i] = reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(channel)}
    }
    for i, channel := range f.expire {
       cases[size + i] = reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(channel)}
    }
    for i, channel := range f.mcast {
        cases[2 * size + i] = reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(channel)}
    }
    i, value, _ := reflect.Select(cases)
    if i < size {
        if value.String() != "CLOSE" {
            // Learned
            for index, pipeline := range f.pipelines {
                if index != i {
                    // no Routing for self
                    pipeline.AddFIBEntry(value.String(),f.pipelines[i].GetName())
                }
            }
        } else {
            f.delPort(i)
        }
    }
    if (i >= size) && (i < size * 2){
        // Expired
        for _, pipeline := range f.pipelines {
            pipeline.DelFIBEntry(value.String())
        }
    }
    // Not dealing with multicast gibberish for now
}


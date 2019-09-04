//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package main

import "os"
import "agent"
import "sync"

func main() {

    a := &agent.NimbessAgent{Mu: &sync.Mutex{}, Pipelines: make(map[string]string),}
    f := agent.NewFIB("testfib", a)

    for count := 1; count < len(os.Args); count++ {
        a.Pipelines[os.Args[count]] = os.Args[count]
        // we add them by hand for now, will change to channel later
        f.AddPort(os.Args[count])
    }

    for true {
        f.Iteration()
    }
}

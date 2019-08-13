//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package main

import "os"
import "pipeline"
import "fib"

func main() {

    f := fib.NewFIB("testfib")

    for count := 1; count < len(os.Args); count++ {
        p := pipeline.NewMockPipeline(os.Args[count])
        f.AddPort(p)
    }

    for true {
        f.Iteration()
    }
}

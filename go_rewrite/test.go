//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package main

import "os"
import "fmt"
import "reflect"
import "reader"

func main() {
    rcount := len(os.Args) - 1
    learn := make([]chan string, 64)
    expire := make([]chan string, 64)
    mcast := make([]chan string, 64)
    rds := make([]*Reader.Reader, 64)
    cases := make([]reflect.SelectCase, 64)

    for count := 1; count < len(os.Args); count++ {
        learn[count - 1] = make(chan string)
        expire[count - 1] = make(chan string)
        mcast[count - 1] = make(chan string)
        rds[count - 1] = Reader.NewReader(os.Args[count], learn[count - 1], expire[count - 1], mcast[count - 1])
        go rds[count - 1].Run()
    }
    for i, channel := range learn {
        cases[i] = reflect.SelectCase{Dir: reflect.SelectRecv, Chan: reflect.ValueOf(channel)}
    }

    for rcount > 0 {
        i, value, ok := reflect.Select(cases)
        fmt.Println("Index ", i, "Value ", value.String())
        if (value.String() == "CLOSE") || (!ok) {
            rd := rds[i]
            _ = copy(learn[i:], learn[i + 1:])
            _ = copy(expire[i:], expire[i + 1:])
            _ = copy(mcast[i:], mcast[i + 1:])
            _ = copy(cases[i:], cases[i + 1:])
            _ = copy(rds[i:], rds[i + 1:])
            learn = learn[:len(learn) - 1]
            expire = expire[:len(expire) - 1]
            mcast = mcast[:len(mcast) - 1]
            cases = cases[:len(cases) - 1]
            rds = rds[:len(rds) - 1]
            rd.Close()
            rcount --
        }
    }
}

//Copyright (c) 2019 Red Hat Inc
//
//License: GPL2, see COPYING in source directory


package main

import "os"
import "fmt"
import "reader"

func main() {
    learn := make(chan string)
    expire := make(chan string)
    mcast := make(chan string)
    rd := Reader.NewReader(os.Args[1], learn, expire, mcast)
    r_active := true
    go rd.Run()
    for r_active {
        select {
            case learned :=  <-learn:
                fmt.Println("Learned MAC:", learned)
                if learned == "CLOSE" {
                    r_active = false
                }
            case expired :=  <-expire:
                fmt.Println("Expired MAC:", expired)
            case mc :=  <-mcast:
                fmt.Println("Mcast Gibberish - TBA:", mc)
        }
    }
    rd.Close()
}

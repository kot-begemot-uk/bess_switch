// Copyright (c) 2019 Red Hat and/or its affiliates.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at:
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Mock Agent runtime

package agent

import (
	"sync"
    "fmt"
)

type NimbessAgent struct {
	Mu         *sync.Mutex
    Pipelines map[string]string // mocking with string should suffice for now
}


func (s *NimbessAgent) AddL2FIBEntry(MAC string, pipeline string, port string) {
    fmt.Println("Add requested for MAC %s pipeline %s port %s", MAC, pipeline, port)
}

func (s *NimbessAgent) DelL2FIBEntry(MAC string, pipeline string) {
    fmt.Println("Del requested for MAC %s pipeline %s port %s", MAC, pipeline)
}

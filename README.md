# bess_switch
Simple switch for BESS

Does only unicast for now, all broadcast and multicast is dropped to slow path
in the underlying linux kernel.

`EXPORT PYTHONPATH=$YOURBESSPATH`
`./switch.py --config config_example.json --verbose 1`

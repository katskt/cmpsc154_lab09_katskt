# ucsbcs154lab9
# All Rights Reserved
# Copyright (c) 2023 Jonathan Balkind
# Distribution Prohibited
import pyrtl

# Pointers, need to be registers because they need to know what they were before.
current_commit_slot = pyrtl.Register(bitwidth = 4, name = "current_commit_slot")
current_alloc_slot = pyrtl.Register(bitwidth = 4, name = "current_alloc_slot")


### Alloc Interface ###
# Is the alloc req valid?
rob_alloc_req_val_i = pyrtl.Input(bitwidth=1, name="rob_alloc_req_val_i")
# Incoming Instruction's Physical dest reg
rob_alloc_req_preg_i = pyrtl.Input(bitwidth=5, name="rob_alloc_req_preg_i")
# Is the ROB ready to accept an incoming request?
rob_alloc_req_rdy_o = pyrtl.Output(bitwidth=1, name="rob_alloc_req_rdy_o")
# The assigned ROB slot
rob_alloc_resp_slot_o = pyrtl.Output(bitwidth=4, name="rob_alloc_resp_slot_o")


### Writeback Interface ###
# Is writeback occuring?
rob_fill_val_i = pyrtl.Input(bitwidth=1, name="rob_fill_val_i")
# In which slot is writeback occurring? 
rob_fill_slot_i = pyrtl.Input(bitwidth=4, name="rob_fill_slot_i")


### Commit Interface ###
# Is an entry being committed this cycle?
rob_commit_wen_o = pyrtl.Output(bitwidth=1, name="rob_commit_wen_o")
# ROB slot that's committed
rob_commit_slot_o = pyrtl.Output(bitwidth=4, name="rob_commit_slot_o")
# Physical register that's committed
rob_commit_rf_waddr_o = pyrtl.Output(bitwidth=5, name="rob_commit_rf_waddr_o")


# metadata managed by this module, don't modify names/ports!
rob_valid = pyrtl.MemBlock(bitwidth=1, addrwidth=4, name="rob_valid", max_write_ports=2)
# rob_pending = pyrtl.MemBlock(bitwidth=1, addrwidth=4, name="rob_pending", max_write_ports=2)
rob_pending = pyrtl.MemBlock(bitwidth=1, addrwidth=4, name="rob_pending", max_write_ports=10, max_read_ports=10)
rob_preg = pyrtl.MemBlock(bitwidth=5, addrwidth=4, name="rob_preg")

x = pyrtl.WireVector(bitwidth = 1, name = "z0p")
x <<= rob_pending[0]
# metadata managed by this module END

#ALLOC
rob_alloc_req_rdy_wv_not = pyrtl.Register(bitwidth = 1, name = "rob_alloc_req_rdy_wv")

rob_alloc_req_rdy_wv_not.next <<= (((current_alloc_slot + 1 ) == current_commit_slot) | ((current_alloc_slot == 15) & (current_commit_slot == 0)))

can_you_alloc = ~rob_alloc_req_rdy_wv_not & rob_alloc_req_val_i
rob_valid[current_alloc_slot] <<= pyrtl.MemBlock.EnabledWrite(enable = can_you_alloc, data=1)
rob_preg[current_alloc_slot] <<= pyrtl.MemBlock.EnabledWrite(enable = can_you_alloc, data=rob_alloc_req_preg_i)
rob_pending[current_alloc_slot] <<= pyrtl.MemBlock.EnabledWrite(enable = can_you_alloc, data=1)

rob_alloc_resp_slot_o <<= current_alloc_slot
rob_alloc_req_rdy_o <<= ~rob_alloc_req_rdy_wv_not

current_alloc_slot.next <<= pyrtl.select(can_you_alloc, pyrtl.select(current_alloc_slot == 15, 0, current_alloc_slot + 1 ),current_alloc_slot)
#COMMIT
# commit logic: is the pending at this placevalid? then output and move. 
# this looks at commit spot. 1 check if current are same. 
move_commit = pyrtl.WireVector(bitwidth = 1, name = "move_commit")
move_commit <<= ((current_commit_slot != current_alloc_slot) & (rob_pending[current_commit_slot] == 0 )& ((rob_fill_val_i == 0) | ((rob_fill_val_i == 1) & (rob_fill_val_i != current_commit_slot))))
current_commit_slot.next <<= pyrtl.select(move_commit, pyrtl.select(current_commit_slot == 15, 0, current_commit_slot + 1), current_commit_slot)
ztemp = pyrtl.WireVector(bitwidth = 1, name = "ztemp")
rob_commit_wen_o <<= move_commit
rob_valid[current_commit_slot] <<= pyrtl.MemBlock.EnabledWrite(enable = move_commit,data= 0)

rob_commit_slot_o <<= pyrtl.select(move_commit, current_commit_slot, 0)
rob_commit_rf_waddr_o <<= pyrtl.select(move_commit, rob_preg[current_commit_slot], 0)

# WRITEBACK

rob_pending[rob_fill_slot_i] <<= pyrtl.MemBlock.EnabledWrite(enable=(rob_fill_val_i), data=0)
ztemp <<= (current_commit_slot != current_alloc_slot)

### Testing and Simulation ###
def TestOneInstructionFullFlow():
    sim_trace = pyrtl.SimulationTrace()
    sim = pyrtl.Simulation(tracer=sim_trace)
    preg = 10
    # First allocate a slot in the ROB
    sim.step({
            rob_alloc_req_val_i: 1,
            rob_alloc_req_preg_i: preg,
            rob_fill_val_i: 0,
            rob_fill_slot_i: 0,
        })
    assert(sim.inspect("rob_alloc_req_rdy_o") == 1)
    assignedSlot = sim.inspect("rob_alloc_resp_slot_o")
    # Then, writeback that slot (could be many cycles later but in this example just one)
    sim.step({
            rob_alloc_req_val_i: 0,
            rob_alloc_req_preg_i: 0,
            rob_fill_val_i: 1,
            rob_fill_slot_i: assignedSlot,
        })
    # We don't commit in the same cycle as writeback happens
    assert(sim.inspect("rob_commit_wen_o") == 0)
    sim.step({
            rob_alloc_req_val_i: 0,
            rob_alloc_req_preg_i: 0,
            rob_fill_val_i: 0,
            rob_fill_slot_i: 0,
        })
    # ...commit in the next cycle
    assert(sim.inspect("rob_commit_wen_o") == 1)
    assert(sim.inspect("rob_commit_slot_o") == assignedSlot)
    assert(sim.inspect("rob_commit_rf_waddr_o") == preg)
    # ROB stays ready
    assert(sim.inspect("rob_alloc_req_rdy_o") == 1)
    
    sim.step({
            rob_alloc_req_val_i: 0,
            rob_alloc_req_preg_i: 0,
            rob_fill_val_i: 0,
            rob_fill_slot_i: 0,
        })
    # but shouldn't commit anything in the following cycle!
    assert(sim.inspect("rob_commit_wen_o") == 0)
    # ...and ROB stays ready
    assert(sim.inspect("rob_alloc_req_rdy_o") == 1)
    sim_trace.render_trace(symbol_len=20)



if __name__ == "__main__":
    TestOneInstructionFullFlow()
    print("Pass TestOneInstructionFullFlow")


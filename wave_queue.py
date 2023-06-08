import hyper_parameters as paras
# from arena import enter_target_update, enter_operation


class WaveQueue(object):
    # board_rate = 0.25 # pax/sec
    SIM_DELTA = paras.sim_delta
    MOVE_UP_STEPS = paras.move_up_steps
    REACT_STEPS = paras.reaction_steps

    def __init__(self):
        self._buses = []
        self._last_pop_time = 0

    def pop_one_bus(self, curr_t):
        self._last_pop_time = curr_t - \
            (WaveQueue.MOVE_UP_STEPS * WaveQueue.SIM_DELTA)
        return self._buses.pop(0)

    def enter_one_bus(self, bus):
        self._buses.append(bus)

    def get_queue_length(self):
        return len(self._buses)

    def get_head_bus(self, curr_t):
        # return "None" if not satisfied
        if curr_t - self._last_pop_time >= (WaveQueue.MOVE_UP_STEPS+WaveQueue.REACT_STEPS) * WaveQueue.SIM_DELTA:
            return self._buses[0]

    def accumulate_delay(self):
        for bus in self._buses:
            if bus.is_moving_target_set == False:
                bus.enter_delay += WaveQueue.SIM_DELTA

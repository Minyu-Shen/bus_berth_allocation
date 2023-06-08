from wave_queue import WaveQueue
from copy import deepcopy


class Signal(object):
    def __init__(self, cycle_length, green_ratio, buffer_size=1000):
        self._cycle_length = cycle_length
        self._green_ratio = green_ratio
        # self._buffer_size = buffer_size # default is infinite; i.e. no impact on the stop
        # self._queue = []

    def is_green(self, curr_t):
        if (curr_t % self._cycle_length) < self._cycle_length*self._green_ratio:
            return True
        else:
            return False


class Up_Buffer(object):
    def __init__(self, buffer_size, up_signal):
        self.up_queue = WaveQueue()
        self.buffer_size = buffer_size
        self.up_signal = up_signal
        # 0 is the most upstream
        self._buses_in_buffer = [None] * buffer_size

    def pop_end_bus(self, curr_t):
        bus = self._buses_in_buffer[-1]
        self._buses_in_buffer[-1] = None
        return bus

    def bus_arrival(self, bus, curr_t):
        bus.arr_up_queue_mmt = curr_t
        bus.arr_system_mmt = curr_t
        self.up_queue.enter_one_bus(bus)

    def get_end_bus(self):
        return self._buses_in_buffer[-1]

    def operation(self, curr_t):
        # fillup most upstream buffer first
        if self.up_signal.is_green(curr_t) and self.up_queue.get_queue_length() > 0:
            bus = self.up_queue.get_head_bus(curr_t)
            if bus is None:
                return
            if self._buses_in_buffer[0] is None:
                self._buses_in_buffer[0] = bus
                self.up_queue.pop_one_bus(curr_t)

        for loc in range(self.buffer_size-1):
            if self._buses_in_buffer[loc+1] == None:
                self._buses_in_buffer[loc+1] = self._buses_in_buffer[loc]
                self._buses_in_buffer[loc] = None


class Buffer(object):
    def __init__(self, buffer_size, down_signal=None, up_signal=None):
        self.buffer_size = buffer_size
        # 0 is the most downstream
        self._buses_in_buffer = [None] * buffer_size
        self.is_invading = False
        self.down_signal = down_signal
        self.up_signal = up_signal
        self.book_no = 0

    def update_time_space_info(self, current_time, berth_num):
        for buffer_id in range(self.buffer_size):
            bus = self._buses_in_buffer[buffer_id]
            if bus is None:
                continue
            bus.trajectory_locations[current_time] = berth_num + buffer_id + 1

    def check_if_can_in(self):
        curr_no = sum(1 for bus in self._buses_in_buffer if bus != None)
        assert self.book_no + curr_no <= self.buffer_size, 'no greater than the buffer size'

        if self.book_no + curr_no == self.buffer_size:  # is full
            return False
        else:
            return True

    def check_final_buffer(self):
        if self._buses_in_buffer[0] is None:
            return None
        else:
            # assert self._buses_in_buffer[0].move_up_step != 0, 'the bus in the buffer cannot be still'
            return self._buses_in_buffer[0].move_up_step

    def set_occupation(self, bus):
        bus.move_up_step = 0
        bus.is_moving_target_set = False
        self._buses_in_buffer[0] = bus
        self.book_no -= 1
        self.is_invading = False

    def discharge(self, curr_t):
        if self.buffer_size > 0:
            # printed_bus_ids = [b.bus_id if b is not None else None for b in self._buses_in_buffer ]
            for loc in range(self.buffer_size-1, -1, -1):
                self._set_target(loc, curr_t)
                self._move_up_operation(loc, curr_t)

    def _move_up_operation(self, loc, curr_t):
        # for loc in range(self.buffer_size-1,-1,-1):
        bus = self._buses_in_buffer[loc]
        if bus is None:
            return
        if bus.is_moving_target_set == False:
            return

        if bus.react_left_step > 0:
            bus.react_left_step -= 1
        else:
            if bus.move_up_step < bus.MOVE_UP_STEPS:
                bus.move_up_step += 1
            else:
                assert bus.move_up_step == bus.MOVE_UP_STEPS, 'must be equal'
                self.forward(loc, curr_t)

    def _set_target(self, loc, curr_t):
        # for loc in range(self.buffer_size-1,-1,-1):
        bus = self._buses_in_buffer[loc]
        if bus is None:
            return
        if bus.is_moving_target_set == True:
            return

        if loc == self.buffer_size-1:
            if self.down_signal.is_green(curr_t):
                bus.react_left_step = 0
                bus.is_moving_target_set = True
        else:
            next_bus = self._buses_in_buffer[loc+1]
            if next_bus is None or next_bus.move_up_step > 0:
                bus.is_moving_target_set = True
                if next_bus is not None:
                    bus.react_left_step = max(
                        bus.REACT_STEPS - next_bus.move_up_step, 0)
                else:
                    bus.react_left_step = 0

    def forward(self, loc, curr_t):
        if loc == self.buffer_size-1:
            self._buses_in_buffer[loc].dpt_system_mmt = curr_t
            self._buses_in_buffer[loc] = None
        else:
            self._buses_in_buffer[loc+1] = self._buses_in_buffer[loc]
            self._buses_in_buffer[loc+1].is_moving_target_set = False
            self._buses_in_buffer[loc+1].move_up_step = 0
            self._buses_in_buffer[loc] = None

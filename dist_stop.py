from stop import Stop
from dist_dwell import DistDwell
from collections import defaultdict

# 'process' for methods for sub-stop
# 'operation' for methods in parent-stop


class DistStop(Stop, DistDwell):
    def __init__(
        self, stop_id, berth_num, queue_rule, route_dists, down_buffer, up_buffer
    ):
        Stop.__init__(self, stop_id, berth_num,
                      queue_rule, down_buffer, up_buffer)
        DistDwell.__init__(self, route_dists)
        self.berth_state = defaultdict(list)

    # 0. inheriting bus_arrival and override, called from outside
    def bus_arrival(self, bus, t):
        Stop.bus_arrival(self, bus, t)
        # generate service time upon arrival in the entry queue
        bus.serv_time = self.get_random_serv_time(
            bus.route
        )  # inherited from 'DistDwell'
        bus.total_service_time = bus.serv_time
        bus.arr_mmt = t
        bus.arr_system_mmt = t

    def _service_process(self, t):
        # update service time for each bus
        for berth_index, bus in enumerate(self._buses_serving):
            if bus == None:
                continue
            if bus.serv_time > 0:
                if bus.service_start_mmt == None:
                    bus.service_start_mmt = t
                bus.serv_time -= bus.SIM_DELTA
                if bus.serv_time <= 0.0:
                    if bus.service_end_mmt == None:
                        bus.service_end_mmt = t
                    if bus.service_berth == None:
                        bus.service_berth = berth_index
                    bus.is_served = True
                    self._remove_from_service_list(bus)

    def process(self, t):
        self.current_time = t

        if self._queue_rule == "FO-Free" and True in self._insertion_marks:
            exit()

        # -1. update the buffer state
        if self._downstream_buffer is not None:
            self._downstream_buffer.discharge(t)

        # 0. update the target berth and target place
        self._update_targets(t)

        # check lane and berth, alternately, from downstream to upstream
        for loc in range(self._berth_num - 1, -1, -1):
            self.berth_state[loc].append(self._insertion_marks[loc])

            # 1. for passing lane
            self._lane_operation(loc)

            # 2. stop (berths) move-up operations
            # if self._berth_moveup_operation(loc) == 'no_service_operation': continue
            self._berth_move_up_operation(loc)

        # 3. stop (berths) service operations
        self._service_process(t)
        # self._entry_queue.operation(t, self)

        self._entry_operation(t)
        # for bus in self._buses_in_berth:
        #     if bus is not None:
        #         print(bus)

        # 4. update upstream buffer state
        if self._upstream_buffer is not None:
            self._upstream_buffer.operation(t)

        # 4. accumulate delays
        # self._accumulate_delays()

        # self.update_time_space(t)

    def _accumulate_delays(self):
        # 1. update enter delay in the queue
        self._entry_queue.accumulate_delay()
        # 2. update delay in the passing lane
        for bus in self._place_buses_running:
            if bus is None:
                continue
            if bus.is_moving_target_set == False:
                if bus.is_served:
                    bus.exit_delay += Stop.SIM_DELTA
                else:
                    bus.enter_delay += Stop.SIM_DELTA
        # 3. update delay in the berth
        for bus in self._buses_in_berth:
            if bus is None:
                continue
            if bus not in self._buses_serving:
                if bus.is_moving_target_set == False:
                    if bus.is_served:
                        bus.exit_delay += Stop.SIM_DELTA
                    else:
                        bus.enter_delay += Stop.SIM_DELTA

    def _remove_from_service_list(self, bus):
        for index, removed_bus in enumerate(self._buses_serving):
            if removed_bus == bus:
                self._buses_serving[index] = None
                break

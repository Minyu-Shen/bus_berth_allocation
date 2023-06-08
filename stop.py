import hyper_parameters as paras
from wave_queue import WaveQueue

# 'process' for methods for sub-stop
# 'operation' for methods in parent-stop

# import line_profiler
# import atexit
# profile = line_profiler.LineProfiler()
# atexit.register(profile.print_stats)


class Stop(object):
    # stop_num = 0
    SIM_DELTA = paras.sim_delta
    MOVE_UP_STEPS = paras.move_up_steps
    REACT_STEPS = paras.reaction_steps

    def __init__(self, stop_id, berth_num, queue_rule, down_buffer, up_buffer):
        self._stop_id = stop_id
        self._berth_num = berth_num
        self._queue_rule = queue_rule
        self._downstream_buffer = down_buffer
        self._upstream_buffer = up_buffer

        # running states for berths
        self.reset()

    def reset(self):
        self._entry_queue = WaveQueue()
        self._buses_in_berth = [
            None
        ] * self._berth_num  # moving buses that are not fully occupying the whole berth
        self._buses_serving = [None] * \
            self._berth_num  # for service time update
        self._insertion_marks = [False] * self._berth_num  # for cut-in
        # the head running in the berth
        self._pre_occupies = [None] * self._berth_num
        self._order_marks = [None] * self._berth_num  # ordered by which berth?

        # running states for lanes
        self._place_buses_running = [
            None
        ] * self._berth_num  # moving buses that are not fully occupying the whole place
        self._place_pre_occupies = [
            None
        ] * self._berth_num  # the head running in the berth
        self._place_order_marks = [None] * self._berth_num

        # stats
        self.exit_counting = 0  # observer at the exit of stop
        self.current_time = 0

    def get_entry_queue_length(self):
        return self._entry_queue.get_queue_length()

    # callable methods outside, to add bus into the stop
    def bus_arrival(self, bus, t):
        self._entry_queue.enter_one_bus(bus)

    ########################## time-space info ##########################
    def update_time_space(self, current_time):

        for bus in self._entry_queue._buses:
            bus.trajectory_locations[current_time] = 0
        for b in range(self._berth_num):
            bus = self._buses_in_berth[b]
            if bus is None:
                continue
            bus.trajectory_locations[current_time] = b + 1
        for place in range(self._berth_num):
            bus = self._place_buses_running[place]
            if bus is None:
                continue
            bus.trajectory_locations[current_time] = 11 + place

        if self._downstream_buffer is not None:
            self._downstream_buffer.update_time_space_info(
                current_time, self._berth_num
            )

    ########################## operations ##########################

    def _berth_discharge(self):
        # record leaving system time for far-side
        if self._downstream_buffer is None:
            self._buses_in_berth[self._berth_num -
                                 1].dpt_system_mmt = self.current_time

        self._buses_in_berth[self._berth_num -
                             1].dpt_stop_mmt = self.current_time
        self._buses_in_berth[self._berth_num - 1] = None
        self._insertion_marks[self._berth_num - 1] = False
        self.exit_counting += 1

    def _lane_discharge(self):
        # record leaving system time for far-side
        if self._downstream_buffer is None:
            self._place_buses_running[self._berth_num -
                                      1].dpt_system_mmt = self.current_time

        self._place_buses_running[self._berth_num -
                                  1].dpt_stop_mmt = self.current_time
        self._place_buses_running[self._berth_num - 1] = None
        self.exit_counting += 1

    def _entry_operation(self, current_time):
        if self._upstream_buffer == None:
            if self._entry_queue.get_queue_length() == 0:
                return
            bus = self._entry_queue.get_head_bus(current_time)
        else:
            bus = self._upstream_buffer.get_end_bus()

        if bus is None:
            return
        self._entry_operation_interaction(bus, current_time)

    def _lane_operation(self, loc):
        bus = self._place_buses_running[loc]
        if bus is None:
            return
        # ! if bus.is_moving_target_set == False: return

        if loc == (self._berth_num - 1):
            if (
                self._downstream_buffer is None
            ):  # directly leave, without updating move_up_step
                self._lane_discharge()
            else:  # has downstream buffer
                if bus.lane_target is not None:
                    state = bus.react_move_operation()
                    if state == "moved":
                        if self._downstream_buffer.buffer_size == 0:
                            self._lane_discharge()  # directly discharge to the signal
                        else:
                            self._downstream_buffer.set_occupation(bus)
                            self._lane_discharge()

        else:  # not the most-downstream space ...
            if bus.wish_berth is not None:  # overtake-in case
                assert self._queue_rule in [
                    "LO-In-Bus",
                    "LO-In-Lane",
                    "FO-Bus",
                    "FO-Lane",
                    "FO-Free",
                ], "must be these rules"
                assert (
                    bus.wish_berth > loc
                ), "wish berth must be greater than current location"
                if bus.berth_target is not None:
                    assert bus.berth_target == loc + 1, "must be the next berth"

                    state = bus.react_move_operation()
                    if state == "reacted":
                        self._pre_occupies[bus.berth_target] = bus
                        self._order_marks[bus.berth_target] = None
                        if self._queue_rule != "FO-Free":
                            self._insertion_marks[bus.berth_target] = True
                    elif state == "moved":
                        self._place_buses_running[loc] = None
                        self._pre_occupies[bus.berth_target] = None
                        self._buses_in_berth[bus.berth_target] = bus
                        bus.reset_state()
                        if bus.wish_berth == loc + 1:
                            bus.wish_berth = None

                else:  # cannot enter the berth
                    if bus.lane_target == loc + 1:  # move the next place
                        state = bus.react_move_operation()
                        if state == "reacted":
                            self._place_pre_occupies[bus.lane_target] = bus
                            self._place_order_marks[loc + 1] = None
                        elif state == "moved":
                            self._place_buses_running[loc] = None
                            self._place_pre_occupies[bus.lane_target] = None
                            self._place_buses_running[bus.lane_target] = bus
                            bus.reset_state()
                    else:
                        assert bus.lane_target == loc, "must wanna be still"

            else:  # wish berth is none, overtake-out case
                assert bus.lane_target is not None, "the bus must have lane target"
                if bus.lane_target > loc:
                    assert bus.lane_target == loc + 1, "target must be neighbor"
                    state = bus.react_move_operation()
                    if state == "reacted":
                        self._place_pre_occupies[bus.lane_target] = bus
                        self._place_order_marks[loc + 1] = None
                    elif state == "moved":
                        self._place_buses_running[loc] = None
                        self._place_pre_occupies[bus.lane_target] = None
                        self._place_buses_running[bus.lane_target] = bus
                        bus.reset_state()
                else:  # lane_target is self, pass
                    pass

    def _berth_move_up_operation(self, loc):
        bus = self._buses_in_berth[loc]
        if bus is None:
            return
        # ! if bus.is_moving_target_set == False: return

        # most downstream berth, check if served
        if loc == (self._berth_num - 1):
            if bus.is_served:
                if (
                    self._downstream_buffer is None
                ):  # directly leave, without updating move_up_step
                    self._berth_discharge()
                else:  # has downstream buffer
                    if bus.berth_target == "leaving":
                        state = bus.react_move_operation()
                        if state == "moved":  # operations for "reacted" is not needed
                            if self._downstream_buffer.buffer_size == 0:
                                self._berth_discharge()  # directly discharge to the signal
                            else:
                                self._downstream_buffer.set_occupation(bus)
                                self._berth_discharge()

            else:  # already the most-downstream stop, start to serve!
                self._buses_serving[loc] = bus
            return

        # not the most-downstream berth ...
        if bus.lane_target is None:  # check if can move to the next berth
            assert bus.berth_target is not None, "at least one target"
            if bus.berth_target > loc:  # has target
                assert bus.berth_target == loc + 1, "target berth is not near"
                state = bus.react_move_operation()
                if state == "reacted":
                    self._pre_occupies[bus.berth_target] = bus
                    self._order_marks[
                        bus.berth_target
                    ] = None  # already head to it, remove order
                elif state == "moved":
                    self._buses_in_berth[loc] = None
                    self._insertion_marks[loc] = False
                    self._pre_occupies[bus.berth_target] = None
                    self._buses_in_berth[bus.berth_target] = bus
                    bus.reset_state()

            else:
                assert bus.berth_target == loc, "must wanna stay in the berth"
                if bus.is_served == False:
                    if bus.assign_berth is None or bus.assign_berth == loc:
                        self._buses_serving[loc] = bus

        else:  # has lane target
            assert (
                bus.lane_target == loc + 1
            ), "if has lane target, must be the next place"
            assert self._queue_rule in [
                "LO-Out",
                "FO-Bus",
                "FO-Lane",
                "FO-Free",
            ], "rules that have lane target"
            assert bus.berth_target is None, "one and only one target"
            assert (
                bus.is_served is True
            ), "must finish service, otherwise will not set lane as target"

            # check the insertion
            if self._insertion_marks[bus.lane_target] == True:
                assert self._queue_rule in [
                    "FO-Bus",
                    "LO-In-Lane",
                    "FO-Lane",
                ], "must be the overtake-in rules"
                assert bus.move_up_step == 0, "the bus should not be in moving"
            else:
                state = bus.react_move_operation()
                if state == "reacting":
                    self._place_pre_occupies[loc + 1] = bus
                elif state == "reacted":
                    self._place_pre_occupies[loc + 1] = bus
                    self._place_order_marks[loc + 1] = None
                elif state == "moved":
                    self._buses_in_berth[loc] = None
                    self._place_pre_occupies[bus.lane_target] = None
                    self._place_buses_running[bus.lane_target] = bus
                    self._insertion_marks[loc] = False
                    bus.reset_state()
                    # bus.move_up_step = 0
                    # bus.is_moving_target_set = False

    def _entry_operation_interaction(self, bus, current_time):
        if bus.lane_target is not None:
            assert (
                bus.wish_berth is not None
            ), "enter the lane only when there is available wish berth"
            assert (
                bus.lane_target == 0
            ), "the lane target must be the most-upstream place"
            state = bus.react_move_operation()
            if state == "reacted":
                self._place_pre_occupies[0] = bus
            elif state == "moved":
                if self._upstream_buffer is None:
                    bus = self._entry_queue.pop_one_bus(current_time)
                else:
                    bus = self._upstream_buffer.pop_end_bus(current_time)
                    bus.serv_time = self.get_random_serv_time(bus.route)
                    bus.total_service_time = bus.serv_time

                self._place_buses_running[0] = bus
                self._place_pre_occupies[0] = None
                bus.reset_state()

        else:  # lane target is None, only FIFO in
            if bus.berth_target is not None:
                assert bus.wish_berth is None, "no wish berth to overtake in"
                assert bus.berth_target == 0, "must be the first berth"
                state = bus.react_move_operation()
                if state == "reacted":
                    self._pre_occupies[0] = bus
                elif state == "moved":
                    if self._upstream_buffer is None:
                        bus = self._entry_queue.pop_one_bus(current_time)
                    else:
                        bus = self._upstream_buffer.pop_end_bus(current_time)
                        bus.serv_time = self.get_random_serv_time(bus.route)
                        bus.total_service_time = bus.serv_time

                    self._buses_in_berth[0] = bus
                    self._pre_occupies[0] = None
                    bus.reset_state()

            else:  # both lane and berth target is not set
                pass

    ########################## target updates ##########################
    def _update_targets(self, current_time):
        for loc in range(self._berth_num - 1, -1, -1):
            ######### update buses in the lane #########
            self._update_lane_target(loc)
            ######### update buses in the berths #########
            self._berth_target_update(loc)
        ######### update buses in the entry queue #########
        self._entry_target_update(current_time)
        # self._entry_queue.target_update(current_time, self)

    def _entry_target_update(self, current_time):
        if (
            self._upstream_buffer == None
        ):  # interaction directly between entry queue and stop
            if self._entry_queue.get_queue_length() == 0:
                return
            bus = self._entry_queue.get_head_bus(current_time)
        else:
            bus = self._upstream_buffer.get_end_bus()

        if bus is None:
            return
        if bus.is_moving_target_set == True:
            return

        self._entry_target_update_interaction(bus)

    def _update_lane_target(self, loc):
        # return ordered berth by the bus in the passing lane
        bus = self._place_buses_running[loc]
        if bus is None:
            return
        if bus.is_moving_target_set == True:
            return
        if bus.move_up_step != 0:
            return  # only update the 'exactly' in the berth (or place)

        if loc == self._berth_num - 1:
            if self._downstream_buffer is None:  # directly leave
                bus.set_target("leaving", None, True, 0)
            else:
                if self._downstream_buffer.buffer_size == 0:
                    if self._downstream_buffer.down_signal.is_green(self.current_time):
                        bus.set_target("leaving", None, True, 0)
                    else:
                        bus.set_target(None, None)
                else:
                    if self._downstream_buffer.is_invading == False:
                        returned_step = self._downstream_buffer.check_final_buffer()
                        if returned_step == 0:
                            bus.set_target(None, None)
                        else:
                            self._downstream_buffer.is_invading = True
                            react_left_step = (
                                0
                                if returned_step is None
                                else max(bus.REACT_STEPS - returned_step, 0)
                            )
                            bus.set_target("leaving", None,
                                           True, react_left_step)
                    else:
                        bus.set_target(None, None)
            return

        # not the most-downstream space ...
        if bus.is_served:  # for overtake-out
            assert self._queue_rule not in [
                "LO-In-Bus",
                "LO-In-Lane",
            ], "bus in the lane with these rules is not served"
            self._check_target_and_set_l2l(loc)
        else:  # not served, for overtake-in only
            assert (
                bus.wish_berth is not None
            ), "wish berth is none, otherwise not be passing lane without being served"
            # update the wish_berth if possible
            assert bus.wish_berth >= loc + 1, "overpass!"
            if bus.assign_berth is not None:
                assert bus.wish_berth == bus.assign_berth, "mush be equal"
            if bus.wish_berth == loc + 1:  # next berth is the wish berth
                can_move_to_berth = False
                bus_in_next_berth = self._buses_in_berth[loc + 1]
                if (
                    self._pre_occupies[loc + 1] is None
                    and self._place_pre_occupies[loc + 1] is None
                ):
                    # the second condition is for cross validation
                    # i.e. check if the some bus is moving from berth towards lane
                    if bus_in_next_berth is None or bus_in_next_berth.move_up_step > 0:
                        can_move_to_berth = True
                        react_left_step = (
                            0
                            if bus_in_next_berth is None
                            else max(
                                bus.REACT_STEPS - bus_in_next_berth.move_up_step, 0
                            )
                        )
                        bus.set_target(None, loc + 1, True, react_left_step)
                        self._remove_old_mark(bus)
                        self._order_marks[loc + 1] = bus
                if can_move_to_berth == False:
                    bus.set_target(loc, None)
            else:  # still far-away the wish berth, to see if can go along the lane
                self._check_target_and_set_l2l(loc)

    def _berth_target_update(self, which_berth):
        bus = self._buses_in_berth[which_berth]
        if bus == None:
            return
        if bus.is_moving_target_set == True:
            return
        # if bus.move_up_step != 0: return # only update the 'exactly' in the berth (or place)

        if bus.is_served:
            # most-downstream berth ...
            if which_berth == (
                self._berth_num - 1
            ):  # most downstream berth, directly leave
                if self._downstream_buffer is None:
                    bus.set_target(None, "leaving", True, 0)
                else:
                    if self._downstream_buffer.buffer_size == 0:
                        if self._downstream_buffer.down_signal.is_green(
                            self.current_time
                        ):
                            bus.set_target(None, "leaving", True, 0)
                        else:
                            bus.set_target(None, None)
                    else:
                        # if self._downstream_buffer.check_if_can_in() and self._downstream_buffer.is_invading == False:
                        if self._downstream_buffer.is_invading == False:
                            returned_step = self._downstream_buffer.check_final_buffer()
                            if returned_step == 0:
                                bus.set_target(None, None)
                            else:
                                react_left_step = (
                                    0
                                    if returned_step is None
                                    else max(bus.REACT_STEPS - returned_step, 0)
                                )
                                bus.set_target(None, "leaving",
                                               True, react_left_step)
                                self._downstream_buffer.is_invading = True
                        else:
                            bus.set_target(None, None)
                return

            # not the most-downstream berth ...
            bus_running_next_berth = self._buses_in_berth[which_berth + 1]
            can_move_to_next_berth = False
            can_move_to_next_place = False
            if (
                bus_running_next_berth == None
                or bus_running_next_berth.move_up_step > 0
            ):  # first check if can FIFO out
                if self._pre_occupies[
                    which_berth + 1
                ] is None and self._check_grab_and_set_for_berth(which_berth):
                    can_move_to_next_berth = True
                    react_left_step = (
                        0
                        if bus_running_next_berth is None
                        else max(
                            bus.REACT_STEPS - bus_running_next_berth.move_up_step, 0
                        )
                    )
                    bus.set_target(None, which_berth + 1,
                                   True, react_left_step)
            else:  # the bus is not moving, check the overtake-out rule
                assert bus_running_next_berth.move_up_step == 0, "wrong"
                if self._pre_occupies[which_berth + 1] is not None:
                    raise SystemExit("Error: conflict-1")
                # check the overtake-out rule
                if self._queue_rule in ["LO-Out", "FO-Bus", "FO-Lane", "FO-Free"]:
                    # check the buffer state
                    buffer_ready = False
                    if self._downstream_buffer is None:
                        buffer_ready = True
                    else:
                        if self._downstream_buffer.buffer_size == 0:
                            if self._downstream_buffer.down_signal.is_green(
                                self.current_time
                            ):
                                buffer_ready = True
                        else:
                            if self._downstream_buffer.check_if_can_in():
                                buffer_ready = True
                    if buffer_ready:
                        (order_place, return_reaction) = self._set_order_and_target_b2l(
                            which_berth
                        )
                        if order_place is not None:
                            can_move_to_next_place = True
                            bus.set_target(order_place, None,
                                           True, return_reaction)
                            self._place_order_marks[order_place] = bus
                            if self._downstream_buffer is not None:
                                self._downstream_buffer.book_no += 1

            if can_move_to_next_berth == False and can_move_to_next_place == False:
                bus.set_target(None, which_berth)

        else:  # the bus is not served
            # most-downstream berth ...
            if which_berth == (self._berth_num - 1):
                bus.set_target(None, which_berth)
                # bus.berth_target = which_berth # stay still and serve
                # bus.lane_target = None
                return

            # not the most-downstream berth ...
            # already in the berth, three cases
            # 1. bus is serving
            if bus in self._buses_serving:
                bus.set_target(None, which_berth)
                # bus.berth_target = which_berth
                # bus.lane_target = None
            else:
                # 2. not advanced to the most-downstream vacant berth yet
                # 2.1 check if it is the assigned berth
                if bus.assign_berth is None or bus.assign_berth > which_berth:
                    # not the assigned case, or the assigned berth is still far-away
                    # then check next berth
                    bus_running_next_berth = self._buses_in_berth[which_berth + 1]
                    can_move_to_next_berth = False
                    if (
                        bus_running_next_berth is None
                        or bus_running_next_berth.move_up_step > 0
                    ):
                        if self._pre_occupies[
                            which_berth + 1
                        ] == None and self._check_grab_and_set_for_berth(which_berth):
                            can_move_to_next_berth = True
                            react_left_step = (
                                0
                                if bus_running_next_berth is None
                                else max(
                                    bus.REACT_STEPS
                                    - bus_running_next_berth.move_up_step,
                                    0,
                                )
                            )
                            bus.set_target(None, which_berth + 1,
                                           True, react_left_step)
                    if can_move_to_next_berth == False:
                        bus.set_target(None, which_berth)
                else:  # the assigned case and assigned berth is the current berth
                    assert (
                        bus.assign_berth == which_berth
                    ), "overpass the assigned berth"
                    bus.set_target(None, which_berth)

    def _check_grab_and_set_for_berth(self, which_berth):
        bus = self._buses_in_berth[which_berth]
        if (
            self._order_marks[which_berth + 1] == None
            or self._order_marks[which_berth + 1] == bus
        ):  # no one order, or ordered by itself, can move to
            # bus.set_target(None, which_berth+1)
            self._remove_old_mark(bus)
            self._order_marks[which_berth + 1] = bus
            return True

        else:  # is already ordered, must be ordered by the bus in the passing lane
            # check if can grab?
            ordered_by_bus = self._order_marks[which_berth + 1]
            # 1. find the bus in the passing lane
            order_location = -1
            for index, bus_i in enumerate(self._place_buses_running):
                if bus_i == ordered_by_bus:
                    order_location = index
            # 2. find the bus in the entry queue (in reaction or moving up)
            is_to_grab = False
            if (
                order_location < which_berth - 1
            ):  # ordered by a far-away bus (must in the passing lane)
                is_to_grab = True
            else:
                if (
                    order_location == which_berth - 1
                    and ordered_by_bus.move_up_step == 0
                ):
                    is_to_grab = True
            if is_to_grab:
                self._remove_old_mark(bus)
                self._order_marks[which_berth + 1] = bus
                # set the one being grabbed
                if order_location == -1:  # the grabbed bus is in the queue
                    ordered_by_bus.reset_state()
                    self._remove_old_mark(ordered_by_bus)
                else:
                    ordered_by_bus.is_moving_target_set = False
                    self._remove_old_mark(ordered_by_bus)
                    if ordered_by_bus.assign_berth is None:
                        ordered_by_bus.wish_berth = which_berth  # transfer old to her
                        self._order_marks[which_berth] = ordered_by_bus
                    else:  # the assigned case
                        ordered_by_bus.wish_berth = (
                            which_berth + 1
                        )  # did not change her wish berth
                return True

            else:  # is ordered and cannot grab, stay still
                return False

    def _set_order_and_target_b2l(self, from_which_berth):
        # return is a 2-element tuple
        # the first element is None or from_which_berth+1,
        # the second element is the reaction time if any
        # check if the adjacent place has bus
        bus = self._buses_in_berth[from_which_berth]
        bus_adjacent = self._place_buses_running[from_which_berth]
        # cross validation
        if (
            self._pre_occupies[from_which_berth + 1] is None
            and self._place_pre_occupies[from_which_berth + 1] is None
        ):
            # and self._order_marks[from_which_berth+1] is None:
            # if bus_adjacent is None or bus_adjacent.move_up_step == 0: # no adjacent bus
            bus_next_place = self._place_buses_running[from_which_berth + 1]
            if bus_next_place is None:  # no adjacent bus and no bus in the next place
                if self._place_order_marks[from_which_berth + 1] == None:
                    if (
                        self._insertion_marks[from_which_berth + 1] == False
                    ):  # the bus in the next berth is fifo in
                        return (from_which_berth + 1, 0)
            else:  # no adjacent bus, but has bus in the next place
                if (
                    bus_next_place.move_up_step > 0
                ):  # the bus in the next place is leaving
                    if self._place_order_marks[from_which_berth + 1] == None:
                        if (
                            self._insertion_marks[from_which_berth + 1] == False
                        ):  # the bus in the next berth is fifo in
                            reaction_time = max(
                                bus.REACT_STEPS - bus_next_place.move_up_step, 0
                            )
                            return (from_which_berth + 1, reaction_time)
        else:
            pass
        return (None, None)

    def _check_ot_in_berth_from_queue(self, check_berth, bus):
        bus_in_berth = self._buses_in_berth[check_berth]
        bus_heading_to_berth = self._pre_occupies[check_berth]
        order_by_bus = self._order_marks[check_berth]
        if bus_in_berth == None:
            if bus_heading_to_berth == None and order_by_bus == None:
                return True
            else:  # the entry queue has the lowest 'grab' power, no need to check 'grab'
                return False
        else:  # the berth is not empty
            # if bus_in_berth.is_moving_target_set == False:
            if bus_in_berth.move_up_step == 0:
                return False
            else:
                if bus_heading_to_berth == None and order_by_bus == None:
                    return True
                else:
                    return False

    def _remove_old_mark(self, bus):
        for index, ordered_bus in enumerate(self._order_marks):
            if ordered_bus == bus:
                self._order_marks[index] = None
                break

    def _check_target_and_set_l2l(self, loc):
        bus = self._place_buses_running[loc]
        bus_next_place = self._place_buses_running[loc + 1]
        if bus_next_place is None:
            # check if any bus in the berth is moving to it
            if (
                self._place_pre_occupies[loc + 1] is None
            ):  # no bus in the berth is heading to it
                # check if the lane is blocked
                if self._insertion_marks[loc + 1] == True and self._queue_rule in [
                    "FO-Lane"
                ]:  # the lane is blocked
                    bus.set_target(loc, None)
                else:  # the lane is not blocked
                    bus.set_target(loc + 1, None, True, 0)
                    self._place_order_marks[loc + 1] = bus
            else:  # one bus is heading to it
                # bus.lane_target = loc
                bus.set_target(loc, None)
        else:  # the next place is not empty
            # if bus_next_place.is_moving_target_set == False:
            if bus_next_place.move_up_step == 0:
                bus.set_target(loc, None)
            else:  # the bus in the next place is moving, follow!
                if (
                    self._place_pre_occupies[loc + 1] is None
                ):  # no bus in the berth is heading to it
                    # check if the lane is blocked
                    if self._insertion_marks[loc + 1] == True and self._queue_rule in [
                        "FO-Lane"
                    ]:  # the lane is blocked
                        bus.set_target(loc, None)
                    else:  # the lane is not blocked
                        react_left_step = max(
                            bus.REACT_STEPS - bus_next_place.move_up_step, 0
                        )
                        bus.set_target(loc + 1, None, True, react_left_step)
                        self._place_order_marks[loc + 1] = bus
                else:  # one bus is heading to it
                    bus.set_target(loc, None)

    def _entry_target_update_interaction(self, bus):
        bus_in_upstream_berth = self._buses_in_berth[0]
        if bus_in_upstream_berth is None or bus_in_upstream_berth.move_up_step > 0:
            react_left_step = (
                0
                if bus_in_upstream_berth is None
                else max(bus.REACT_STEPS - bus_in_upstream_berth.move_up_step, 0)
            )
            bus.set_target(None, 0, True, react_left_step)
            bus.wish_berth = None
        else:  # the bus in the upstream berth will be still
            # check if can overtake into the berth
            head_bus_can_move = False
            if self._queue_rule in ["LO-In-Bus", "FO-Bus", "FO-Lane", "LO-In-Lane", "FO-Free"]:
                bus_in_upstream_place = self._place_buses_running[0]
                if (
                    bus_in_upstream_place == None
                    or bus_in_upstream_place.move_up_step > 0
                ):
                    for b in range(self._berth_num - 1, 0, -1):
                        can_ot_in = self._check_ot_in_berth_from_queue(b, bus)
                        if can_ot_in == True:
                            if bus.assign_berth is None or b == bus.assign_berth:
                                head_bus_can_move = True
                                react_left_step = (
                                    bus.REACT_STEPS
                                    if bus_in_upstream_place == None
                                    else max(
                                        bus.REACT_STEPS
                                        - bus_in_upstream_place.move_up_step,
                                        0,
                                    )
                                )
                                bus.set_target(0, None, True, react_left_step)
                                bus.wish_berth = b
                                self._remove_old_mark(bus)
                                self._order_marks[b] = bus
                                break

            if head_bus_can_move == False:
                bus.set_target(None, None)

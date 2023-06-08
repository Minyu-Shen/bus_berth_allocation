import hyper_parameters as paras
from collections import defaultdict


class Bus(object):
    # board_rate = 0.25 # pax/sec
    SIM_DELTA = paras.sim_delta
    MOVE_UP_STEPS = paras.move_up_steps
    REACT_STEPS = paras.reaction_steps

    def __init__(self, bus_id, route, berth=None):
        self.bus_id = bus_id
        self.route = route
        self.assign_berth = berth

        # stats, for corridor, it should be changed to a list, future work ...
        self.arr_system_mmt = None
        self.dpt_system_mmt = None

        self.arr_up_queue_mmt = None  # the time when a bus arrives at upstream-signal queue
        self.arr_mmt = None  # the time when a bus arrives in the entry queue
        self.service_start_mmt = None  # the time when a bus enters the berth to serve
        self.total_service_time = None
        self.service_end_mmt = None  # the time when a bus finishes service
        self.dpt_stop_mmt = None  # the time when a bus leaves stop
        self.enter_delay = 0.0
        self.exit_delay = 0.0

        # 'leaving', '1', '2', ... target berth
        self.berth_target = None
        self.lane_target = None
        self.is_served = False
        self.wish_berth = None
        self.is_moving_target_set = False
        self.serv_time = -1.0

        # traffic characteristics in stop
        self.move_up_step = 0
        self.reaction_step = None
        self.react_left_step = None

        # trajectory
        self.trajectory = []
        self.trajectory_times = []
        self.lane_trajectory = []
        self.lane_trajectory_times = []
        self.trajectory_locations = defaultdict(float)
        self.service_berth = None

    def react_move_operation(self):
        if self.react_left_step > 0:
            self.react_left_step -= 1
            return "reacting"
        else:
            if self.move_up_step == 0:
                self.move_up_step += 1
                return "reacted"
            else:
                self.move_up_step += 1
                if (
                    self.move_up_step == self.MOVE_UP_STEPS
                ):  # has already reached the next loc
                    return "moved"
                else:
                    return "moving"

    def reset_state(self):
        self.react_left_step = None
        self.berth_target = None
        self.lane_target = None
        self.move_up_step = 0
        self.is_moving_target_set = False

    def set_target(
        self, lane_target, berth_target, is_moving_target_set=False, react_step=0
    ):
        self.lane_target = lane_target
        self.berth_target = berth_target
        self.is_moving_target_set = is_moving_target_set
        self.react_left_step = react_step

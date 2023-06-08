import time
from numpy import random
from sim_results import get_delay_of_continuous
from arena import (
    cal_berth_f_rho_for_each_plan,
    get_run_df_from_db,
    get_run_df_from_near_stop_db,
)
from line_profile import get_generated_line_info
from region import build_region_tree


class Opt_Stats(object):
    def __init__(self, curr_promising_region_id, curr_depth, sim_budget):
        self.sim_budget = sim_budget
        self.evaled_assign_plans = []
        self.eval_count = 0

        self.curr_depth = curr_depth
        self.min_delay_so_far = 1.0e4
        self.history_min_delays = []
        self.curr_promising_region_id = curr_promising_region_id

    def add_eval_info(self, assign_plan, delay):
        if assign_plan not in self.evaled_assign_plans:
            self.eval_count += 1
            self.evaled_assign_plans.append(assign_plan)
            self.min_delay_so_far = min(self.min_delay_so_far, delay)
            self.history_min_delays.append(self.min_delay_so_far)
        else:
            pass

    def is_budget_run_out(self):
        print("current eval count:", self.eval_count)
        return False if self.eval_count < self.sim_budget else True


def apply_cnp_algo(algo_setting, stop_setting, signal_setting=None):
    # isolated stop setting
    (queue_rule, berth_num, line_num, set_no) = stop_setting
    # algorithm hyper-parameters
    sim_budget, max_depth, sample_num_of_each_region = algo_setting

    # build tree
    total_region_list = build_region_tree(dim=berth_num, max_depth=max_depth)
    root_region = total_region_list[0]
    # root_region.print_tree()

    # get profile and simulated data
    line_flow, line_service, line_rho = get_generated_line_info(
        berth_num, line_num, set_no
    )
    sim_info = {
        "queue_rule": queue_rule,
        "berth_num": berth_num,
        "line_flow": line_flow,
        "line_service": line_service,
        "signal": None,
    }
    if signal_setting is None:
        run_df = get_run_df_from_db(stop_setting)
    else:
        cycle_length, green_ratio, buffer_size, is_near = signal_setting
        sim_info["signal"] = {
            "cycle_length": cycle_length,
            "green_ratio": green_ratio,
            "buffer_size": buffer_size,
            "is_near": is_near,
        }
        run_df = get_run_df_from_near_stop_db(stop_setting, signal_setting)

    # algorithm start
    algo_start_time = time.time()

    # find start point and its located region of maximum depth
    curr_promising_region_id = -1
    curr_depth = -1
    regions_at_max_depth = [
        region for region in total_region_list if region.depth == max_depth - 1
    ]
    total_rho = sum(line_rho.values())
    evenest_point = [total_rho / berth_num] * berth_num

    assign_plan, delay = get_delay_of_continuous(
        line_flow, line_service, evenest_point, run_df, sim_info
    )
    print("even point's delay is:", delay)
    berth_flow, berth_rho = cal_berth_f_rho_for_each_plan(
        berth_num, assign_plan, line_flow, line_service
    )
    for region in regions_at_max_depth:
        unit_berth_rho = [x / total_rho for x in berth_rho]
        is_contain = region.is_point_in_region(unit_berth_rho)
        if is_contain:
            curr_promising_region_id = region.region_id
            curr_depth = region.depth

    opt_stats = Opt_Stats(curr_promising_region_id, curr_depth, sim_budget)
    print("start promising region is:", curr_promising_region_id)
    opt_stats.add_eval_info(assign_plan, delay)
    # print(
    #     "--------- start region is: ", opt_stats.curr_promising_region_id, "-----------"
    # )

    ######### start iteration #########
    # print(opt_stats.min_delay_so_far, opt_stats.eval_count)
    print("--------- start iteration -----------")
    while True:
        if opt_stats.is_budget_run_out():
            break
        curr_promising_region = total_region_list[opt_stats.curr_promising_region_id]
        if curr_promising_region.depth == 0:  # at root node
            # print("--------- at root -----------")
            best_child_region_tuple = curr_promising_region.evaluate_children_return_best(
                sample_num_of_each_region,
                line_flow,
                line_service,
                opt_stats,
                run_df,
                sim_info,
            )
            best_child_region_id, best_delay_list = best_child_region_tuple
            opt_stats.curr_promising_region_id = best_child_region_id
        else:
            # evaluate "combined" big surrounding region
            surrounding_sample_delays = []
            surrounding_region_list = [
                region
                for region in total_region_list
                if region.depth == curr_promising_region.depth
                and region.region_id != curr_promising_region.region_id
            ]
            for _ in range(sample_num_of_each_region):
                # uniformly select one surrounding region
                sampled_region = random.choice(surrounding_region_list)
                assign_plan, delay = sampled_region.sample_one_plan(
                    line_flow, line_service, run_df, sim_info
                )
                opt_stats.add_eval_info(assign_plan, delay)
                surrounding_sample_delays.append(delay)

            # calculate promising index of surround region
            surr_mean = sum(surrounding_sample_delays) / \
                len(surrounding_sample_delays)

            if curr_promising_region.depth == max_depth - 1:  # at leaf node
                # print("--------- at max depth -----------")
                promising_sample_delays = []
                # further explore promising region
                for _ in range(sample_num_of_each_region):
                    assign_plan, delay = curr_promising_region.sample_one_plan(
                        line_flow, line_service, run_df, sim_info
                    )
                    opt_stats.add_eval_info(assign_plan, delay)
                    promising_sample_delays.append(delay)

                # compare indexs and see if trackback or not
                promising_mean = sum(promising_sample_delays) / len(
                    promising_sample_delays
                )
                if min(surrounding_sample_delays) < min(promising_sample_delays):
                    # if surr_mean < promising_mean:
                    opt_stats.curr_promising_region_id = (
                        curr_promising_region.parent.region_id
                    )
                # print(opt_stats.curr_promising_region_id)

            else:  # 0 < curr_depth < max_depth-1
                # print("---------at intermedium depth-----------")
                best_child_region_tuple = curr_promising_region.evaluate_children_return_best(
                    sample_num_of_each_region,
                    line_flow,
                    line_service,
                    opt_stats,
                    run_df,
                    sim_info,
                )
                best_child_region_id, best_delay_list = best_child_region_tuple
                best_child_mean = sum(best_delay_list) / len(best_delay_list)

                if min(surrounding_sample_delays) < min(best_delay_list):
                    # if surr_mean < best_child_mean:
                    opt_stats.curr_promising_region_id = (
                        curr_promising_region.parent.region_id
                    )
                else:
                    opt_stats.curr_promising_region_id = best_child_region_id
    print("--------- end iteration -----------")
    # print(opt_stats.min_delay_so_far, opt_stats.eval_count)

    print("cnp algorithm running time is:", time.time() - algo_start_time)

    return opt_stats.history_min_delays

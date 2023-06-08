import time
import math
from numpy import random
from sim_results import get_delay_of_discrete_plan
from arena import (
    cal_berth_f_rho_for_each_plan,
    get_run_df_from_db,
    get_run_df_from_near_stop_db,
    assign_plan_enumerator,
    random_assign_plan_enumerator,
)
from line_profile import get_generated_line_info
import random
from region import build_region_tree


class Opt_Stats(object):
    def __init__(self):
        self.evaled_assign_plans = []
        self.eval_count = 0

        self.min_delay_so_far = 1.0e6
        self.history_min_delays = []

    def add_eval_info(self, assign_plan, delay):
        if assign_plan not in self.evaled_assign_plans:
            self.eval_count += 1
            self.evaled_assign_plans.append(assign_plan)
            self.min_delay_so_far = min(self.min_delay_so_far, delay)
            self.history_min_delays.append(self.min_delay_so_far)
        else:
            pass


def get_global_min_delay(stop_setting, signal_setting=None):
    if signal_setting is None:
        run_df = get_run_df_from_db(stop_setting)
    else:
        run_df = get_run_df_from_near_stop_db(stop_setting, signal_setting)
    run_df["final_delay"] = run_df.delay_seq.apply(
        lambda x: x[-1] if type(x) is not float else 1000.0
    )
    # print(type(run_df["final_delay"].min()))
    return run_df["final_delay"].min().item()


def apply_tan_algo(algo_setting, stop_setting, signal_setting=None):
    ### isolated stop setting
    (queue_rule, berth_num, line_num, set_no) = stop_setting
    ### algorithm hyper-parameters
    # if berth_num > 2, radius is out of use
    radius, region_num = algo_setting
    depth = int(math.log(region_num, berth_num))

    ### get profile and simulated data
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

    ### algorithm start
    algo_start_time = time.time()

    ### create optimization stats object for recording
    opt_stats = Opt_Stats()

    ### divide set into subsets
    ### for c=2, center -> plans, for c=3, region_id -> plans
    subset_plans_dict = {}
    if berth_num == 2:
        for s in range(1, region_num + 1, 1):
            center = s * 2 * radius - radius
            subset_plans_dict[center] = []

        ### assign plans to subset
        iterator = assign_plan_enumerator(line_num, berth_num)
        for plan in iterator:
            berth_flow, _ = cal_berth_f_rho_for_each_plan(
                berth_num, plan, line_flow, line_service
            )
            ratio = berth_flow[1] / berth_flow[0]
            for s in range(1, region_num + 1, 1):
                # for s in range(region_num, 0, -1):
                center = s * 2 * radius - radius
                if abs(ratio - center) < radius:
                    subset_plans_dict[center].append(plan)
                    break
        # for subset_center, plans in subset_plans_dict.items():
        #     print(subset_center, " : ", len(plans))

    else:
        total_region_list = build_region_tree(dim=berth_num, max_depth=depth + 1)
        regions_at_max_depth = [
            region for region in total_region_list if region.depth == depth
        ]
        for region in regions_at_max_depth:
            subset_plans_dict[region] = []
        ### assign plans to subset
        iterator = random_assign_plan_enumerator(line_num, berth_num, sample_num=20000)
        for plan in iterator:
            berth_flow, _ = cal_berth_f_rho_for_each_plan(
                berth_num, plan, line_flow, line_service
            )
            berth_flow = [x / sum(berth_flow) for x in berth_flow]

            for region in regions_at_max_depth:
                if len(subset_plans_dict[region]) < 100:
                    if region.is_point_in_region(berth_flow):
                        subset_plans_dict[region].append(plan)
                        break
                else:
                    continue

    # keys = list(subset_plans_dict.keys())
    # random.shuffle(keys)
    # shuffled_subset_plans_dict = {key: subset_plans_dict[key] for key in keys}
    shuffled_subset_plans_dict = subset_plans_dict

    print("--------- start iteration -----------")
    sample_no = 5
    best_delay_so_far = 1.0e6
    ### get a general view, i.e, sample 5 for each subset
    subset_delay_metric = {}
    for the_key, plans in shuffled_subset_plans_dict.items():
        # if the set no. is smallert than 5, no need to look at it
        if len(plans) < sample_no:
            continue
        rand_samp_plans = random.sample(plans, sample_no)
        subset_sum = 0.0
        for rand_samp_plan in rand_samp_plans:
            delay = get_delay_of_discrete_plan(rand_samp_plan, run_df, sim_info)
            opt_stats.add_eval_info(rand_samp_plan, delay)
            best_delay_so_far = min(best_delay_so_far, delay)
            subset_sum += delay
        subset_delay_metric[the_key] = subset_sum / sample_no

    ### continue exploring the most promising subset
    promising_subset_key = min(subset_delay_metric.items(), key=lambda x: x[1])[0]
    promising_subset_plans_list = subset_plans_dict[promising_subset_key]

    while len(promising_subset_plans_list) >= sample_no:
        rand_plans_list = random.sample(promising_subset_plans_list, sample_no)
        promising_subset_plans_list = [
            x for x in promising_subset_plans_list if x not in rand_plans_list
        ]  # delete the sampled ones
        subset_min = 1.0e6
        # evaluate the plans
        for rand_plan in rand_plans_list:
            delay = get_delay_of_discrete_plan(rand_plan, run_df, sim_info)
            subset_min = min(subset_min, delay)
            opt_stats.add_eval_info(rand_plan, delay)

        if subset_min <= best_delay_so_far:
            best_delay_so_far = subset_min
        else:
            break

    # print(opt_stats.history_min_delays)
    print("--------- end iteration -----------")

    print("Tan's algorithm running time is:", time.time() - algo_start_time)

    return opt_stats.history_min_delays

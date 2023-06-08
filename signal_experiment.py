from sacred import Experiment
from signal_scenario import sim_one_NS_scenario, sim_one_FS_scenario
from line_profile import get_generated_line_info
import ast

signal_ex = Experiment()


@signal_ex.automain
def main(
    queue_rule,
    berth_num,
    line_num,
    set_no,
    cycle_length,
    green_ratio,
    buffer_size,
    is_near,
    assign_plan_str,
):
    print("------------------------ start main ----------------------------")
    flows, services, rhos = get_generated_line_info(
        berth_num, line_num, set_no)
    is_persistent = False
    assign_plan = ast.literal_eval(assign_plan_str)
    args = (
        berth_num,
        queue_rule,
        flows,
        services,
        is_persistent,
        buffer_size,
        cycle_length,
        green_ratio,
        assign_plan,
    )
    delay_seq = sim_one_NS_scenario(
        *args) if is_near else sim_one_FS_scenario(*args)
    signal_ex.info["delay_seq"] = delay_seq
    print("delay_seq is:", delay_seq)
    return delay_seq[-1]

    # ex.info['test'] = 'testing'

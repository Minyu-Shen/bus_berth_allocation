from bus_generator import Generator
from dist_stop import DistStop
import hyper_parameters as paras
from arena import calculate_avg_delay, check_convergence

# from multiprocessing import Pool, cpu_count, Process

# def sim_one_isolated_scenario(berth_num, queue_rule, flows, services, persistent, assign_plan):


def sim_one_isolated_scenario(*args):
    queue_rule, berth_num, flows, services, is_persistent, assign_plan = args
    ######## hyper-parameters ########
    max_tolerance_delay = paras.max_tolerance_delay  # seconds
    each_eval_interval = 3600 * 10
    total_eval_num = 60  # 400
    epoch_num = each_eval_interval * total_eval_num  # the total number of epochs

    minimum_eval_num = 20  # 150
    minimum_epoch_num = minimum_eval_num * each_eval_interval
    # if the last *std_num* of mean_seq is greater than threshold, return
    std_num = 20  # 20
    threshold = 0.05

    ######## simulation ########
    # duration = int(epoch_num / paras.sim_delta)
    duration = int(epoch_num * paras.sim_delta)
    generator = Generator(flows, duration, assign_plan)
    stop = DistStop(0, berth_num, queue_rule, services, None, None)
    total_buses = []
    mean_seq = []
    for epoch in range(0, epoch_num, 1):
        t = epoch * paras.sim_delta
        # operation at the stop ...
        stop.process(t)

        # dispatch process ...
        if is_persistent:
            # the capacity case, keep the entry queue length == berth_num
            while stop.get_entry_queue_length() < berth_num:
                bus = generator.dispatch(t, persistent=True)
                total_buses.append(bus)
                stop.bus_arrival(bus, t)
        else:
            # according to arrival table
            dispatched_buses = generator.dispatch(t)
            for bus in dispatched_buses:
                total_buses.append(bus)
                stop.bus_arrival(bus, t)

        # evaluate the convergence
        if epoch % each_eval_interval == 0 and epoch != 0:
            if is_persistent:
                mean_seq.append(stop.exit_counting / (t * 1.0) * 3600)
            else:
                mean_seq.append(calculate_avg_delay(total_buses))
            if mean_seq[-1] >= max_tolerance_delay:
                return mean_seq
            if epoch > minimum_epoch_num:
                if check_convergence(mean_seq[-std_num:], threshold):
                    return mean_seq

    # reset for next round
    # stop.reset()
    # generator.reset()
    # total_buses = []

    # return (assign_plan, mean_seq[-1])
    return mean_seq


"""

def test():
    ######### parameters ########
    berth_num = 4
    total_bus_flow = 140.0  # buses/hr
    mu_S = 25  # seconds
    line_num = 4
    persistent = False
    assign_plan = {0: 0, 1: 1, 2: 2, 3: 3}  # line -> berth
    # assign_plan = None
    flows, services = generate_line_info(line_num, total_bus_flow, mu_S)

    # flows = {0: [f/4, 1.0], 1:[f/4, 1.0], 2:[f/4, 1.0], 3:[f/4, 1.0]} # [buses/hr, c.v.]
    # services = {0: [mu_S, c_S], 1: [mu_S, c_S], 2: [mu_S, c_S], 3: [mu_S, c_S]}

    ######### for plotting time-space diagram ########
    # queue_rule = 'FO-Bus'
    # res = sim_one_isolated_scenario(berth_num, queue_rule, flows, services, persistent, assign_plan)

    ### plot settings
    line_styles = ["-", ":", "--", "-."]
    rules = ["FIFO", "LO-Out", "FO-Bus", "FO-Lane"]
    rule2style = {rules[i]: line_styles[i] for i in range(len(rules))}

    ######### for desire ########
    # rules = ['FIFO', 'LO-Out', 'FO-Bus', 'FO-Lane']
    rules = ["FIFO", "LO-Out", "FO-Bus"]

    if persistent:
        c_Ss = [0.1 * x for x in range(11)]
        rule_capacities = {}
        for queue_rule in rules:
            capacities = []
            for c_S in c_Ss:
                print(c_S)
                services = {0: [mu_S, c_S]}
                cpt = sim_one_isolated_scenario(
                    berth_num, queue_rule, flows, services, persistent, assign_plan
                )
                capacities.append(cpt)
            rule_capacities[queue_rule] = capacities
        print(rule_capacities)

        # plotting ...
        plt, ax = set_x_y_draw("C_S", "buses/hr")
        for rule, capacities in rule_capacities.items():
            if rule == "FO-Lane":
                plt.plot(c_Ss, capacities, "r", linestyle=rule2style[rule], linewidth=2)
            else:
                plt.plot(c_Ss, capacities, "k", linestyle=rule2style[rule], linewidth=2)
        ax.legend(
            [r"FIFO", r"LO-Out", r"FO-Bus", r"FO-Lane"], handlelength=3, fontsize=13
        )
        plt.show()
    else:
        c_Ss = [0.1 * x for x in range(11)]
        rule_delays = {}
        for queue_rule in rules:
            delays = []
            for c_S in c_Ss:
                services = {
                    0: [mu_S, c_S],
                    1: [mu_S, c_S],
                    2: [mu_S, c_S],
                    3: [mu_S, c_S],
                }
                print(c_S)
                delay = sim_one_isolated_scenario(
                    berth_num, queue_rule, flows, services, persistent, assign_plan
                )
                delays.append(delay)
            rule_delays[queue_rule] = delays
        print(rule_delays)

        # plotting ...
        plt, ax = set_x_y_draw("C_S", "delay (secs)")
        for rule, delays in rule_delays.items():
            if rule == "FO-Lane":
                plt.plot(c_Ss, delays, "r", linestyle=rule2style[rule], linewidth=2)
            else:
                plt.plot(c_Ss, delays, "k", linestyle=rule2style[rule], linewidth=2)

        ax.legend(rules, handlelength=3, fontsize=13)

        plt.show()
"""


if __name__ == "__main__":
    pass

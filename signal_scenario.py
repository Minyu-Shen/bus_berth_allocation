from re import A
from bus_generator import Generator
from dist_stop import DistStop
from signal import Signal, Buffer, Up_Buffer

# from queue import Buffer
import hyper_parameters as paras
import matplotlib.pyplot as plt
from arena import calculate_avg_delay, check_convergence


def sim_one_FS_scenario(
    berth_num,
    queue_rule,
    flows,
    services,
    is_persistent,
    buffer_size,
    cycle_length,
    green_ratio,
    assign_plan=None,
):

    ######## hyper-parameters ########
    print(assign_plan)
    print("d=", buffer_size, "C=", cycle_length, "g=", green_ratio)
    max_tolerance_delay = paras.max_tolerance_delay  # seconds
    each_eval_interval = 3600 * 10
    total_eval_num = 600
    epoch_num = total_eval_num * each_eval_interval  # the total number of epochs

    minimum_eval_num = 150
    minimum_epoch_num = minimum_eval_num * each_eval_interval
    # 20 # if the last *std_num* of mean_seq is greater than threshold, return
    std_num = 30
    threshold = 0.01

    ######## simulation ########
    duration = int(epoch_num * paras.sim_delta)
    generator = Generator(flows, duration, assign_plan)
    up_signal = Signal(cycle_length, green_ratio)
    up_buffer = Up_Buffer(buffer_size, up_signal)
    stop = DistStop(0, berth_num, queue_rule, services,
                    down_buffer=None, up_buffer=up_buffer)

    total_buses = []
    mean_seq = []
    # duration = int(3600 * 0.2)
    for epoch in range(0, duration, 1):
        t = epoch * paras.sim_delta
        ##### from downstream to upstream #####
        # operation at the stop, including downstream buffer if any ...
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
            # added to the upstream buffer
            for bus in dispatched_buses:
                total_buses.append(bus)
                up_buffer.bus_arrival(bus, t)

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

    return mean_seq


def sim_one_NS_scenario(
    berth_num,
    queue_rule,
    flows,
    services,
    is_persistent,
    buffer_size,
    cycle_length,
    green_ratio,
    assign_plan=None,


):

    ######## hyper-parameters ########
    print("simulating near-side case ... ")
    print(assign_plan)
    print("d=", buffer_size, "C=", cycle_length, "g=", green_ratio)
    max_tolerance_delay = paras.max_tolerance_delay  # seconds
    each_eval_interval = 3600 * 10
    total_eval_num = 80  # 600
    epoch_num = total_eval_num * each_eval_interval  # the total number of epochs

    minimum_eval_num = 20  # 150
    minimum_epoch_num = minimum_eval_num * each_eval_interval
    # 20 # if the last *std_num* of mean_seq is greater than threshold, return
    std_num = 20
    threshold = 0.05

    ######## simulation ########
    duration = int(epoch_num * paras.sim_delta)
    generator = Generator(flows, duration, assign_plan)
    down_signal = Signal(cycle_length, green_ratio)
    down_buffer = Buffer(buffer_size, down_signal)
    stop = DistStop(0, berth_num, queue_rule, services, down_buffer, None)
    total_buses = []
    mean_seq = []
    # duration = int(3600 * 0.2)
    for epoch in range(0, duration, 1):
        t = epoch * paras.sim_delta
        ##### from downstream to upstream #####
        # operation at the stop, including downstream buffer if any ...
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
            # directly added to the first stop
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

    # if duration < 1800:
    #     plot_NS_time_space(
    #         berth_num,
    #         total_buses,
    #         duration,
    #         paras.sim_delta,
    #         stop,
    #         down_buffer,
    #         down_signal,
    #     )

    return mean_seq


def plot_NS_time_space(
    berth_num, total_buses, duration, sim_delta, stop, down_buffer, down_signal
):
    colors = ["r", "g", "b", "y", "k", "w"]
    count = 0
    sorted_list = sorted(total_buses, key=lambda x: x.bus_id, reverse=False)
    # plot the insertion mark
    for berth, times in stop.berth_state.items():
        for i in range(len(times) - 1):
            if times[i] == True or times[i + 1] == True:
                plt.hlines(
                    berth + 1, i * sim_delta, (i + 1) * sim_delta, "r", linewidth=8
                )

    # print(len(sorted_list))
    for bus in sorted_list:
        j = count % 5
        # j = bus.assign_berth
        lists = sorted(
            bus.trajectory_locations.items()
        )  # sorted by key, return a list of tuples
        x, y = zip(*lists)  # unpack a list of pairs into two tuples
        x_list = list(x)
        y_list = list(y)
        for i in range(len(x) - 1):
            y_1 = y_list[i] - 10 if y_list[i] > 8 else y_list[i]
            y_2 = y_list[i + 1] - 10 if y_list[i + 1] > 8 else y_list[i + 1]
            y_tuple = (y_1, y_2)
            x_tuple = (x_list[i], x_list[i + 1])

            if y_list[i + 1] > 8:
                plt.plot(x_tuple, y_tuple,
                         colors[j], linestyle="dotted", linewidth=1)
            else:
                plt.plot(x_tuple, y_tuple, colors[j])
        # plot the service time
        if bus.service_berth is not None:
            plt.hlines(
                (bus.service_berth + 1),
                bus.service_start_mmt,
                bus.service_end_mmt,
                "gray",
                linewidth=5,
            )

        count += 1

    # plot signal
    C = down_signal._cycle_length
    G = down_signal._green_ratio * C
    R = C - G
    for i in range(int(duration) // C):
        # plot green period
        plt.hlines(
            berth_num + 1 + down_buffer.buffer_size,
            i * C,
            i * C + G,
            linewidth=2.5,
            colors="g",
        )
        # plot red period
        plt.hlines(
            berth_num + 1 + down_buffer.buffer_size,
            i * C + G,
            (i + 1) * C,
            linewidth=2.5,
            colors="r",
        )

    # plot buffer

    plt.show()


if __name__ == "__main__":
    pass

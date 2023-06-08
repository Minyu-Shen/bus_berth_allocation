from algo_experiment import algo_ex


@algo_ex.config
def config():
    seed = 0
    berth_num = 2
    line_num = 12

    # signal
    # signal_paras = None
    # signal_paras = {"cycle_length": 120, "green_ratio": 0.5, "buffer_size": 3}

    is_near = True

    # cycle_length = None
    # green_ratio = None
    # buffer_size = None

    cycle_length = 120
    green_ratio = 0.5
    buffer_size = 3

    # the following two is dynamically changing
    algorithm = None
    queue_rule = None
    set_no = None


# for set_no in [0, 1, 4]:
for set_no in [2, 3]:
    # for queue_rule in ["FO-Free"]:
    for queue_rule in ["FIFO", "LO-Out", "FO-Free"]:
        for algorithm in ["Tan", "CNP"]:
            algo_ex.run(config_updates={
                        "set_no": set_no, "queue_rule": queue_rule, "algorithm": algorithm})

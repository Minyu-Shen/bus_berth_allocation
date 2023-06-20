import matplotlib.pyplot as plt
import numpy as np
from pymongo import MongoClient
import random

random.seed(0)


def generate_line_info(
    line_num,
    total_arrival,
    arrival_type,
    service_type,
    mean_service,
    arr_scale,
    service_scale,
    arrival_cvs=(1.0, 1.0),
    service_cvs=(0.4, 0.8),
):
    np.random.seed(666)
    """
    total_arrival - buses/hr
    mean_service - seconds
    arr_scale - # larger scale, smaller variance of arrival flow mean
    service_scale - # larger scale, smaller variance of service time mean
    """
    # arrival line infos
    if line_num == 1:
        return {0: [total_arrival, arrival_cvs[0]]}, {0: [mean_service, service_cvs[0]]}

    arr_flows = (
        np.random.dirichlet(np.ones(line_num) * arr_scale, size=1).squeeze()
        * total_arrival
    )
    print("generated arrival flows are:", arr_flows)
    print("generated arrival flow std is:", arr_flows.std())

    # service line infors
    service_means = (
        np.random.dirichlet(np.ones(line_num) *
                            service_scale, size=1).squeeze()
        * mean_service
        * line_num
    )
    print("generated service means are:", service_means)
    print("generated service mean std is:", service_means.std())
    flow_infos = {}
    service_infos = {}

    # align
    arr_flows = sorted(arr_flows, reverse=True)
    service_means = sorted(service_means, reverse=False)
    print("sorted arrival flows are:", arr_flows)
    print("sorted service means are:", service_means)
    plt.plot(arr_flows, service_means)
    plt.show()

    for i in range(line_num):
        arr_cv = (
            arrival_cvs[0]
            if arrival_cvs[0] == arrival_cvs[1]
            else np.random.uniform(arrival_cvs[0], arrival_cvs[1])
        )
        flow_infos[str(i)] = (arr_flows[i], arr_cv, arrival_type)
        service_cv = (
            service_cvs[0]
            if service_cvs[0] == service_cvs[1]
            else np.random.uniform(service_cvs[0], service_cvs[1])
        )
        service_infos[str(i)] = (service_means[i], service_cv, service_type)

    return flow_infos, service_infos


def get_generated_line_info(berth_num, line_num, set_no):
    client = MongoClient("localhost", 27017)
    db = client["inputs"]
    collection = db["line_profile"]
    query_dict = {
        "berth_num": berth_num,
        "line_num": line_num,
        "set_no": set_no,
    }
    results = collection.find(query_dict)[0]
    # convert the string of line to int, (because MongoDB only support str as key)
    line_flow = {int(ln): flow for ln, flow in results["line_flow"].items()}
    line_service = {int(ln): service for ln,
                    service in results["line_service"].items()}
    line_rho = {
        ln: (line_flow[ln][0] / 3600.0) * line_service[ln][0] for ln in line_flow
    }
    return line_flow, line_service, line_rho


def generate_and_add_to_db(set_no, arr_cvs, serv_cvs, arr_scale, service_scale):
    # larger scale, smaller variance of arrival flow mean
    client = MongoClient("localhost", 27017)
    db = client["inputs"]
    collection = db["ggg"]

    berth_num = 2
    line_num = 12
    total_flow = 135
    arrival_type = "Gamma"
    service_type = "Gamma"
    mean_service = 25

    line_flow, line_service = generate_line_info(
        line_num,
        total_flow,
        arrival_type,
        service_type,
        mean_service,
        arr_scale,
        service_scale,
        arrival_cvs=arr_cvs,
        service_cvs=serv_cvs,
    )
    json_dict = {}
    json_dict["berth_num"] = berth_num
    json_dict["line_num"] = line_num
    json_dict["set_no"] = set_no
    json_dict["total_flow"] = total_flow
    json_dict["arrival_type"] = arrival_type
    json_dict["service_type"] = service_type
    json_dict["mean_service"] = mean_service
    json_dict["line_flow"] = line_flow
    json_dict["line_service"] = line_service

    # collection.insert_one(json_dict)

    # bar plots
    arrival_flow_list = []
    service_list = []
    for ln, flow in line_flow.items():
        arrival_flow_list.append(flow[0])
        service_list.append(line_service[ln][0])

    # print(service_list)
    x = np.arange(len(line_flow))
    width = 0.25
    fig, ax = plt.subplots()
    flow_bar = ax.bar(
        x - 0.5 * width, arrival_flow_list, width, label="arrival bus flow (buses/hr)",
    )
    # ax2 = ax.twinx()
    service_bar = ax.bar(
        x + 0.5 * width,
        service_list,
        width,
        color="r",
        label="mean service time (seconds)",
    )
    ax.legend()
    # ax2.legend()
    # fig.savefig("figs/line_info.jpg")
    plt.show()


def add_CHT_to_db(line_num=19):
    client = MongoClient("localhost", 27017)
    db = client["inputs"]
    collection = db["line_profile"]

    berth_num = 4
    arrival_type = "Gamma"
    service_type = "Gamma"
    set_no = 0
    # arr_scale = 4  # larger scale, smaller variance of arrival flow mean
    # service_scale = 4  # larger scale, smaller variance of service mean
    if line_num == 16:
        # arr_flows = [8, 2, 2, 6, 6, 2, 2, 1, 4, 1, 1, 4, 5, 1, 1, 1]
        arr_flows = [8, 2, 2, 6, 6, 2, 2, 1, 4, 1, 1, 4, 5, 1, 1, 1]
        service_means = [
            40.0,
            52.0,
            61.0,
            40.0,
            68.3,
            64.0,
            49.0,
            80.0,
            24.25,
            77.0,
            63.0,
            31.0,
            60.0,
            44.0,
            34.0,
            25.0,
        ]
    elif line_num == 19:
        arr_flows = [8, 8, 2, 11, 6, 6, 2, 2,
                     3, 4, 14, 1, 4, 5, 2, 10, 1, 8, 1]
        service_means = [
            40.0,
            50.75,
            52.0,
            84.8,
            40.0,
            68.33,
            64.0,
            49.0,
            76.0,
            24.25,
            58.43,
            63.0,
            31.25,
            60.2,
            52.5,
            58.6,
            34.0,
            56.29,
            25.0,
        ]
    else:
        arr_flows = [12, 2, 7, 7, 3, 3, 7, 2, 4, 9, 3, 3]
        service_means = [
            38.67,
            52.0,
            38.71,
            67.0,
            53.67,
            59.67,
            25.14,
            46.0,
            31.25,
            53.11,
            23.33,
            26.33,
        ]
    arr_flows = [x / (45 / 60) for x in arr_flows]
    line_flow = {}
    line_service = {}
    for i in range(line_num):
        arr_cv = np.random.uniform(0.4, 0.8)
        service_cv = np.random.uniform(0.4, 0.8)
        line_flow[str(i)] = (arr_flows[i], arr_cv, arrival_type)
        line_service[str(i)] = (service_means[i], service_cv, service_type)

    json_dict = {}
    json_dict["berth_num"] = berth_num
    json_dict["line_num"] = line_num
    json_dict["set_no"] = set_no
    json_dict["total_flow"] = None
    json_dict["arrival_type"] = arrival_type
    json_dict["service_type"] = service_type
    json_dict["mean_service"] = None
    json_dict["line_flow"] = line_flow
    json_dict["line_service"] = line_service

    collection.insert_one(json_dict)

    # line_berth_plan = {
    #     "101": "b",
    #     "103": "d",
    #     "106": "b",
    #     "107": "c",
    #     "108": "c",
    #     "109": "d",
    #     "111": "b",
    #     "113": "d",
    #     "115": "b",
    #     "116": "c",
    #     "170": "e",
    #     "182": "e",
    # }


def manual_add_to_db():
    client = MongoClient("localhost", 27017)
    db = client["inputs"]
    collection = db["line_profile"]

    berth_num = 2
    line_num = 12
    total_flow = 135  # 135, 155
    flow_expand_ratio = total_flow / 135.0
    # arrival_type = "Poisson"
    arrival_type = "Gamma"
    service_type = "Gamma"
    # service_type = "Lognormal"
    mean_service = 25

    mean_flow_set_01 = [20.437, 16.265, 7.095, 10.512, 18.132,
                        5.800, 22.514, 6.082, 9.004, 7.836, 4.256, 7.069]

    mean_times_set_0 = [22.447, 25.108, 25.178, 26.020, 27.055,
                        24.030, 23.789, 25.775, 25.206, 24.334, 26.085, 24.974]

    # mean_flow_set_2 = [20.011, 18.478, 16.756, 15.340,
    #                    10.829, 9.596, 8.618, 7.987, 7.964, 7.106, 6.856, 5.452]
    # mean_times_set_2 = [12.870, 18.496, 19.621, 21.105, 24.416,
    #                     25.144, 25.525, 25.680, 28.935, 30.396, 30.793, 37.014]
    
    mean_flow_set_2 = [18.478, 7.106, 7.964, 9.596, 6.856, 16.756, 15.34, 7.987, 10.829, 20.011, 5.452, 8.618]
    mean_times_set_2 = [18.496, 30.396, 28.935, 25.144, 30.793, 19.621, 21.105, 25.68, 24.416, 12.87, 37.014, 25.525]

    # avg = sum(mean_times_set_2) / len(mean_times_set_2)
    # beta = 0.1
    # flows = []
    # for x in mean_times_set_2:
    #     rand_beta = random.uniform(beta*0.6, beta*1.4)
    #     flow = 3600 * rand_beta / x
    #     flows.append(flow)
    # factor = sum(flows) / 135
    # flows = [x / factor for x in flows]

    # flow_sec = [x / 3600 for x in mean_flow_set_012]
    # beta = line_num * 25 / sum([1/x for x in flow_sec])
    # mean_times_set_2 = []
    # for x in flow_sec:
    #     rand_beta = random.uniform(beta*0.6, beta*1.4)
    #     mean_time = rand_beta / x
    #     mean_times_set_2.append(mean_time)

    line_flow = {}
    line_service = {}
    set_no = 2
    for line in range(line_num):
        line_flow[str(line)] = (mean_flow_set_2[line]
                                * flow_expand_ratio, 0.6, arrival_type)
        line_service[str(line)] = (mean_times_set_2[line], 0.6, service_type)

    json_dict = {}
    json_dict["berth_num"] = berth_num
    json_dict["line_num"] = line_num
    json_dict["set_no"] = set_no
    json_dict["total_flow"] = total_flow
    json_dict["arrival_type"] = arrival_type
    json_dict["service_type"] = service_type
    json_dict["mean_service"] = mean_service
    json_dict["line_flow"] = line_flow
    json_dict["line_service"] = line_service

    collection.insert_one(json_dict)


if __name__ == "__main__":
    # add_CHT_to_db(line_num=12)

    manual_add_to_db()

    # line_flow, line_service = generate_line_info(
    #     line_num=12, total_arrival=135, arrival_type="Gamma", service_type="Gamma", mean_service=25, arr_scale=3, service_scale=10)

    # generate_and_add_to_db(
    #     set_no=0,
    #     arr_cvs=(0.6, 0.6),
    #     serv_cvs=(0.6, 0.6),
    #     arr_scale=3,
    #     service_scale=20,
    # )

    # mean_flow_set_3 = [
    #     23.566,
    #     21.744,
    #     1.348,
    #     3.214,
    #     3.067,
    #     5.307,
    #     0.033,
    #     1.536,
    #     0.218,
    #     6.550,
    #     54.950,
    #     13.473,
    # ]

    # mean_flow_set_4 = [
    #     13.807,
    #     12.822,
    #     10.105,
    #     11.246,
    #     13.275,
    #     9.603,
    #     14.263,
    #     9.717,
    #     10.770,
    #     10.372,
    #     8.924,
    #     10.100,
    # ]

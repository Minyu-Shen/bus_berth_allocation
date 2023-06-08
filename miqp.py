from threading import main_thread
import cvxpy as cp
import numpy as np
from line_profile import get_generated_line_info
import math


def get_closest_discrete_from_continuous(
    line_flow, line_service, continuous_rhos, by="rho"
):
    """
    line_flow_mean - dict: ln -> info tuple
    line_service_mean - dict: ln -> info tuple
    continuous_rhos - list of rho decion vector
    """
    line_rho = {ln: line_flow[ln][0] / 3600.0 * line_service[ln][0] for ln in line_flow}
    line_num = len(line_flow)
    berth_num = len(continuous_rhos)

    x = cp.Variable((line_num * berth_num, 1), boolean=True)
    constrs = []
    # all the lines must be assigned to one berth
    sum_x = 0
    for ln in range(line_num):
        one_line_for_all_berths_idx = range(ln * berth_num, (ln + 1) * berth_num, 1)
        for ln_berth_idx in one_line_for_all_berths_idx:
            sum_x += x[ln_berth_idx, 0]
        constrs.append(sum_x == 1)
        sum_x = 0

    # at least one line should be assigned to each berth
    sum_x = 0
    for berth in range(berth_num):
        for idx in range(berth, berth_num * line_num, berth_num):
            sum_x += x[idx]
        constrs.append(sum_x >= 1)
        sum_x = 0

    A = np.zeros((berth_num, berth_num * line_num))
    for berth in range(berth_num):
        for ln_idx in range(line_num):
            A[berth, berth + ln_idx * berth_num] = line_rho[ln_idx]
    # print(A)

    b = np.array(continuous_rhos).reshape(-1, 1)
    # print(b)

    objective = cp.Minimize(cp.sum_squares(A @ x - b))

    prob = cp.Problem(objective, constrs)
    prob.solve()
    # print(x.value)
    # print(A @ x.value)
    # print(objective.value)

    # arrange decision vector to assign_plan dict
    assign_plan = {}
    for ln in range(line_num):
        one_line_for_all_berths_idx = range(ln * berth_num, (ln + 1) * berth_num, 1)
        for ln_berth_idx in one_line_for_all_berths_idx:
            if x.value[ln_berth_idx, 0] == 1 or math.isclose(
                x.value[ln_berth_idx, 0], 1.0, abs_tol=0.01
            ):
                assign_plan[ln] = ln_berth_idx - ln * berth_num
    return assign_plan


if __name__ == "__main__":
    berth_num = 2
    line_num = 6
    line_flow, line_service, line_rhos = get_generated_line_info(
        berth_num, line_num, 135, "Gaussian", 25, 0
    )
    line_flow_mean = {ln: flow[0] for ln, flow in line_flow.items()}
    line_service_mean = {ln: service[0] for ln, service in line_service.items()}

    line_rho = {
        ln: line_flow_mean[ln] / 3600.0 * line_service_mean[ln] for ln in line_flow_mean
    }
    total_rho = sum(line_rho.values())
    b = np.array([total_rho] * berth_num) / berth_num

    assign_plan = get_closest_discrete_from_continuous(
        line_flow_mean, line_service_mean, b
    )


# import numpy as np
# path_attraction = np.array([1, 2, 3]).reshape(3, 1)
# probs = np.exp(path_attraction) / np.sum(np.exp(path_attraction))
# print(probs)

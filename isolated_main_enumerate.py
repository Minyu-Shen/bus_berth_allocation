from experiment import ex
from sacred.observers import MongoObserver
from concurrent import futures
from arena import assign_plan_enumerator


@ex.config
def config():
    seed = 0
    # "FIFO", "LO-Out", "FO-Bus", "FO-Lane"
    # queue_rule = "FIFO"
    # queue_rule = "LO-Out"
    queue_rule = "FO-Free"
    berth_num = 2
    line_num = 12
    set_no = 3
    is_CNP = False


def run(assign_plan_str):
    if not ex.observers:
        ex.observers.append(MongoObserver(url="localhost:27017", db_name="c2"))
        # ex.observers.append(MongoObserver(url="localhost:27017", db_name="ggg"))
    print(assign_plan_str)
    run = ex.run(config_updates={"assign_plan_str": assign_plan_str})


line_num, berth_num = config()["line_num"], config()["berth_num"]
enumerator = assign_plan_enumerator(line_num, berth_num)
assign_plans = [plan for plan in enumerator]
# assign_plans = assign_plans[0:1]
# assign_plans = [None]

with futures.ProcessPoolExecutor(max_workers=28) as executor:
    tasks = [executor.submit(run, str(assign_plan))
             for assign_plan in assign_plans]
    for future in futures.as_completed(tasks):
        pass


# for assign_plan in assign_plans:
#     run(str(assign_plan))

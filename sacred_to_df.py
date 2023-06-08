from collections import OrderedDict
import pandas as pd
import re


def slice_dict(d, keys):
    """Returns a dictionary ordered and sliced by given keys
    keys can be a list, or a CSV string
    """
    if isinstance(keys, str):
        keys = keys[:-1] if keys[-1] == "," else keys
        keys = re.split(", |[, ]", keys)

    return dict((k, d[k]) for k in keys)


def sacred_to_df(
    db_runs, mongo_query=None,
):
    """
    db_runs is usually db.runs
    returns a dataframe that summarizes the experiments, where
    config and info fields are flattened to their keys.
    Summary DF contains the following columns:
    _id, experiment.name, **config, result, **info, status, start_time
    """
    # get all experiment according to mongo query and represent as a pandas DataFrame
    df = pd.DataFrame(list(db_runs.find(mongo_query)))

    # Take only the interesting columns
    df = df.loc[
        :, "_id, experiment, config, result, info, status, start_time".split(", ")
    ]

    def _summerize_experiment(s):
        o = OrderedDict()
        o["_id"] = s["_id"]
        o["name"] = s["experiment"]["name"]
        o.update(s["config"])
        for key, val in s["info"].items():
            if key != "metrics":
                o[key] = val

        o.update(slice_dict(s.to_dict(), "result, status, start_time"))
        return pd.Series(o)

    sum_list = []
    for ix, s in df.iterrows():
        sum_list.append(_summerize_experiment(s))
    df_summary = pd.DataFrame(sum_list).set_index("_id")

    return df_summary

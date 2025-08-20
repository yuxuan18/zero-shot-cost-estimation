import json
import numpy as np

def count_number_of_joins(plan: dict):
    n_joins = 0
    stack = [plan]
    while stack:
        current = stack.pop()
        if "join" in current["plan_parameters"]["op_name"].lower():
            n_joins += 1
        for child in current.get("children", []):
            stack.append(child)
    return n_joins

def count_depth_of_plan(plan: dict):
    max_depth = 0
    stack = [(plan, 1)]
    while stack:
        current, depth = stack.pop()
        max_depth = max(max_depth, depth)
        for child in current.get("children", []):
            stack.append((child, depth + 1))
    return max_depth

def has_agg_after_join_func(plan: dict):
    stack = [(plan, False)]
    while stack:
        current, join_found = stack.pop()
        op_name = current["plan_parameters"]["op_name"].lower()
        if "agg" in op_name and join_found:
            return True
        if "join" in op_name:
            join_found = True
        for child in current.get("children", []):
            stack.append((child, join_found))
    return False

def collect_workload_statistics(plans: list):
    statistics = {}
    for plan in plans:
        query_id = plan["query_id"]
        if query_id not in statistics:
            statistics[query_id] = {"n_tables_in_joins": 0, "depth": 0, "has_agg_after_join": False}
        n_tables_in_joins = count_number_of_joins(plan) + 1
        depth = count_depth_of_plan(plan)
        has_agg_after_join = has_agg_after_join_func(plan)
        if has_agg_after_join:
            statistics[query_id]["has_agg_after_join"] = True
        if n_tables_in_joins > statistics[query_id]["n_tables_in_joins"]:
            statistics[query_id]["n_tables_in_joins"] = n_tables_in_joins
        if depth > statistics[query_id]["depth"]:
            statistics[query_id]["depth"] = depth
    n_tables_in_joins = [stat["n_tables_in_joins"] for stat in statistics.values()]
    depth = [stat["depth"] for stat in statistics.values()]
    has_agg_after_join = [stat["has_agg_after_join"] for stat in statistics.values()]
    return n_tables_in_joins, depth, has_agg_after_join


if __name__ == "__main__":
    with open("data/tpch/test_data.json", "r") as f:
        tpch_plans = json.load(f)["parsed_plans"]
    with open("data/tpcds/test_data.json", "r") as f:
        tpcds_plans = json.load(f)["parsed_plans"]
    with open("data/devmind/devmind_test_data.json", "r") as f:
        devmind_plans = json.load(f)["parsed_plans"]

    tpch_join_tables, tpch_depth, tpch_has_agg_after_join = collect_workload_statistics(tpch_plans)
    tpcds_join_tables, tpcds_depth, tpcds_has_agg_after_join = collect_workload_statistics(tpcds_plans)
    devmind_join_tables, devmind_depth, devmind_has_agg_after_join = collect_workload_statistics(devmind_plans)
    print(f"TPCH: Min/Max/Avg Join Tables: {min(tpch_join_tables)}, {max(tpch_join_tables)}, {np.mean(tpch_join_tables)}, Avg Depth: {np.mean(tpch_depth)}, % Has Agg After Join: {np.mean([1 if x else 0 for x in tpch_has_agg_after_join])}")
    print(f"TPCDS: Min/Max/Avg Join Tables: {min(tpcds_join_tables)}, {max(tpcds_join_tables)}, {np.mean(tpcds_join_tables)}, Avg Depth: {np.mean(tpcds_depth)}, % Has Agg After Join: {np.mean([1 if x else 0 for x in tpcds_has_agg_after_join])}")
    print(f"Devmind: Min/Max/Avg Join Tables: {min(devmind_join_tables)}, {max(devmind_join_tables)}, {np.mean(devmind_join_tables)}, Avg Depth: {np.mean(devmind_depth)}, % Has Agg After Join: {np.mean([1 if x else 0 for x in devmind_has_agg_after_join])}")

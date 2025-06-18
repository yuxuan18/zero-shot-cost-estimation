from krypton_utils.parse_plans import parse_plan
from krypton_utils.convert_plans import convert_to_zero_shot

import os
import json
import glob
import argparse


def read_plan(file_name, model_archi: str="zero_shot", dataset_name: str="tpch"):
    with open(file_name, 'r') as f:
        plan_str = f.read()
    
    plan_dict = parse_plan(plan_str)
    
    if model_archi == "zero_shot":
        parsed_plan = convert_to_zero_shot(plan_dict, dataset_name)
    else:
        raise ValueError(f"Unsupported model architecture: {model_archi}")

    return parsed_plan

def find_plans(plan_path, qid: str = None):
    """
    Find all plan files in the given directory.
    """
    if qid is None:
        plan_files = glob.glob(os.path.join(plan_path, '**/*.out'), recursive=True)
    else:
        plan_files = glob.glob(os.path.join(plan_path, f'plan_q{qid}/*.out'), recursive=True)
    return plan_files

def split_plan(plan: dict):
    plans = []
    stack = [plan]
    while stack:
        current_plan = stack.pop()
        plans.append(current_plan)
        if "children" in current_plan:
            stack.extend(current_plan["children"])
    return plans

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Preprocess Krypton plans for zero-shot model.")
    parser.add_argument('plan_path', type=str, help='Path to the plan file to preprocess.')
    parser.add_argument('--model_archi', type=str, default='zero_shot', help='Model architecture to use for preprocessing.')
    parser.add_argument('--query_id', type=str, default=None, help='Query ID to use for preprocessing.')
    parser.add_argument('--enable_subplan', action='store_true', help='Enable subplan splitting.')
    args = parser.parse_args()

    plan_files = find_plans(args.plan_path, args.query_id)
    hash_set = set()
    parsed_plans = []
    for plan_file in plan_files:
        parsed_plan = read_plan(plan_file, args.model_archi)
        if args.enable_subplan:
            parsed_sub_plans = split_plan(parsed_plan)
            for sub_plan in parsed_sub_plans:
                # if sub_plan["plan_parameters"]["op_name"] == "MergingAggregatedStep":
                #     continue
                subplan_hash = hash(str(sub_plan))
                if subplan_hash not in hash_set:
                    hash_set.add(subplan_hash)
                    parsed_plans.append(sub_plan)
        else:
            plan_hash = hash(str(parsed_plan))
            if plan_hash not in hash_set:
                hash_set.add(plan_hash)
                parsed_plans.append(parsed_plan)
    
    with open("krypton_utils/tpch_stats.json") as f:
        tpch_stats = json.load(f)
    
    workload_info = {
        "parsed_plans": parsed_plans,
        "database_stats": tpch_stats,
        "run_kwargs": {
            "hardware": "cpu"
        }
    }

    with open("workload_tpch.json", "w") as f:
        json.dump(workload_info, f, indent=4)

    print(f"Processed {len(parsed_plans)} unique plans from {len(plan_files)} files.")
    
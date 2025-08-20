import json
import argparse
from tqdm import tqdm

def is_scan_join_filter_only(plan: dict):
    other_operators = ["LimitStep", "AggregatingStep", "SetOperationStep"]
    stack = [plan]
    while stack:
        current = stack.pop()
        if current["plan_parameters"]["op_name"] in other_operators:
            return False
        for child in current.get("children", []):
            stack.append(child)
    return True

def colid2table(col_id: int, col2id: dict):
    if "," in col_id:
        col_id = col_id.split(",")[0]
    for tabcol, cid in col2id.items():
        if cid == int(col_id):
            return tabcol.split('.')[0]
    raise ValueError(f"Column ID {col_id} not found in col2id mapping: {col2id}")

def colid2name(col_id: int, col2id: dict):
    if "," in col_id:
        col_id = col_id.split(",")[0]
    for tabcol, cid in col2id.items():
        if cid == int(col_id):
            return tabcol
    raise ValueError(f"Column ID {col_id} not found in col2id mapping: {col2id}")

def decode_operator(op: str):
    return op.encode("utf-8").decode("unicode_escape")

def extract_tables_from_predicate(predicate: dict, col2id: dict):
    tables = set()
    if predicate["column"]:
        tables.add(colid2table(predicate["column"], col2id))
    if predicate["r_literal"]["type"] == "column":
        tables.add(colid2table(predicate["r_literal"]["literal"], col2id))
    for child in predicate.get("children", []):
        tables.update(extract_tables_from_predicate(child, col2id))
    return tables

def extract_tables(plan: dict, col2id: dict):
    tables = set()
    stack = [plan]
    while stack:
        current = stack.pop()
        if "filter_columns" in current["plan_parameters"]:
            tables.update(extract_tables_from_predicate(current["plan_parameters"]["filter_columns"], col2id))
        for child in current.get("children", []):
            stack.append(child)
    return list(tables)

def extract_join_conditions_from_predicate(predicate: dict, col2id: dict):
    join_conditions = set()
    if predicate["column"] and predicate["r_literal"]["type"] == "column":
        left_col = colid2name(predicate["column"], col2id)
        right_col = colid2name(predicate["r_literal"]["literal"], col2id)
        operator = decode_operator(predicate["operator"])
        join_conditions.add(f"{left_col}={right_col}")
    for child in predicate.get("children", []):
        join_conditions.update(extract_join_conditions_from_predicate(child, col2id))
    return join_conditions

def extract_join_conditions(plan: dict, col2id: dict):
    join_conditions = set()
    stack = [plan]
    while stack:
        current = stack.pop()
        if "Join" in current["plan_parameters"]["op_name"]:
            if "filter_columns" in current["plan_parameters"]:
                join_conditions.update(extract_join_conditions_from_predicate(current["plan_parameters"]["filter_columns"], col2id))
        for child in current.get("children", []):
            stack.append(child)
    return join_conditions

def extract_column_predicates_from_predicate(predicate: dict, col2id: dict, literal_min_max: dict):
    column_predicates = set()
    if predicate["column"] and predicate["r_literal"]["type"] != "column":
        column_name = colid2name(predicate["column"], col2id)
        if "NULL" in predicate["operator"]:
            if "NOT" in predicate["operator"]:
                column_predicates.add(f"{column_name},!=,0")
            else:
                column_predicates.add(f"{column_name},=,0")
        else:
            min_val = literal_min_max.get(str(predicate["column"]), [None, None])["min"]
            max_val = literal_min_max.get(str(predicate["column"]), [None, None])["max"]
            operator = decode_operator(predicate["operator"])
            value = predicate["r_literal"]["literal"]
            if min_val is not None and max_val is not None:
                value = min_val + (max_val - min_val) * float(value) 
            column_predicates.add(f"{column_name},{operator},{value}")
    for child in predicate.get("children", []):
        column_predicates.update(extract_column_predicates_from_predicate(child, col2id, literal_min_max))
    return column_predicates

def extract_column_predicates(plan: dict, col2id: dict, literal_min_max: dict):
    column_predicates = set()
    stack = [plan]
    while stack:
        current = stack.pop()
        if "filter_columns" in current["plan_parameters"]:
            column_predicates.update(extract_column_predicates_from_predicate(current["plan_parameters"]["filter_columns"], col2id, literal_min_max))
        for child in current.get("children", []):
            stack.append(child)
    return column_predicates

def get_col2id_mapping(dataset: str):
    if dataset == "tpch":
        from krypton_utils.tpch import col2id
    elif dataset == "tpcds":
        from krypton_utils.tpcds import col2id
    elif dataset == "devmind":
        from krypton_utils.devmind import col2id
    else:
        raise ValueError(f"Unsupported dataset: {dataset}")
    return col2id

def convert_plans_to_grasp(plans: list, dataset: str = "tpch", hashcodes: list = None, literal_min_max: dict = None):
    grasp_plans = []
    selected_plans = []
    col2id = get_col2id_mapping(dataset)

    assert not hashcodes or len(hashcodes) == len(plans), "Hashcodes length must match plans length"

    for plan, hashcode in tqdm(zip(plans, hashcodes)):
        if not is_scan_join_filter_only(plan):
            continue
        selected_plans.append(plan)
        # extract tables
        tables = extract_tables(plan, col2id)
        # extract join conditions
        join_conditions = extract_join_conditions(plan, col2id)
        # extract column predicates
        column_predicates = extract_column_predicates(plan, col2id, literal_min_max)
        # extract cardinality
        card = plan["plan_runtime"] if not hashcode else hashcode.strip()
        # form a data
        data = f'{",".join(tables)}#{",".join(join_conditions)}#{",".join(column_predicates)}#{card}'
        grasp_plans.append(data)
    return grasp_plans, selected_plans

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert plans to GRASP format")
    parser.add_argument("--input_file", type=str, help="Path to the input JSON file containing plans")
    parser.add_argument("--output_file", type=str, help="Path to the output JSON file for GRASP plans")
    parser.add_argument("--hashcode_file", type=str, help="Path to the hashcode file (not used in current implementation)", default=None)
    parser.add_argument("--dataset", type=str, default="tpch", help="Dataset to use for column ID mapping (tpch, tpcds, devmind)")
    args = parser.parse_args()

    with open(args.input_file) as f:
        test_data = json.load(f)
        plans = test_data["parsed_plans"]

    print(f"Total plans: {len(plans)}")

    if args.hashcode_file:
        with open(args.hashcode_file) as f:
            hashcodes = f.readlines()
        print(f"Total hashcodes: {len(hashcodes)}")
        assert len(hashcodes) == len(plans), "Number of hashcodes must match number of plans"
    else:
        hashcodes = [None] * len(plans)

    if args.dataset == "tpch":
        with open("data/tpch/literal_min_max.json") as f:
            literal_min_max = json.load(f)
    elif args.dataset == "tpcds":
        with open("data/tpcds/literal_min_max.json") as f:
            literal_min_max = json.load(f)
    elif args.dataset == "devmind":
        with open("data/devmind/literal_min_max.json") as f:
            literal_min_max = json.load(f)

    grasp_plans, selected_plans = convert_plans_to_grasp(plans, args.dataset, hashcodes, literal_min_max)

    with open(args.output_file, "w") as f:
        for line in grasp_plans:
            f.write(line + "\n")

    selected_plan_file = args.input_file.replace(".json", "_selected.json")
    test_data["parsed_plans"] = selected_plans
    with open(selected_plan_file, "w") as f:
        json.dump(test_data, f, indent=2)

    print(f"Converted {len(grasp_plans)} plans to GRASP format and saved to {args.output_file}")
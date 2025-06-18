operator_mapping = {
    "lessorequals": "<=",
    "less": "<",
    "equals": "=",
    "ilike": "=",
    "notilike": "!=",
    "greater": ">",
    "greaterorequals": ">=",
    "notequals": "!=",
    "in": "IN"
}

logical_operator = {"and", "or"}
comparison_operator = {">", "<", "<=", "=", ">=", "!="}

aggs = set("count, sum, avg, min, max".split(", "))

def outputcol_to_id(output_col: str, column_id_mapping: dict):
    output_col = output_col.lower()
    found_cols = []
    for col in column_id_mapping:
        idx = output_col.find(col)
        if idx != -1:
            found_cols.append(col)
        else:
            idx = output_col.find("." + col.split(".")[-1])
            if idx != -1:
                found_cols.append(col)
    if len(found_cols) == 0:
        if output_col == "$a$1.$c$1":
            found_cols = ["partsupp.ps_partkey"]
        elif output_col == "$a$1.$c$2":
            found_cols = ["partsupp.ps_suppkey"]
    return [column_id_mapping[col] for col in found_cols]

def outputcol_to_agg(output_col: str, agg_list: list):
    found_idx = -1
    found_agg = 'None'
    for agg in agg_list:
        idx = output_col.find(agg + "(")
        if idx != -1:
            if found_idx == -1 or idx < found_idx:
                found_idx = idx
                found_agg = agg
                break
    return found_agg

def JoinConjucts_to_filter_columns(join_conjuncts: list, column_id_mapping: dict):
    filters = []
    for join_conjunct in join_conjuncts:
        ftr = {
            "column": outputcol_to_id(join_conjunct[1], column_id_mapping)[0],
            "operator": join_conjunct[0],
            "literal": join_conjunct[2],
            "literal_feature": 0,
            "children": []
        }
        filters.append(ftr)
    if len(filters) > 1:
        return {
            "column": None,
            "operator": "AND",
            'literal': None,
            'literal_feature': None,
            "children": filters
        }
    else:
        return filters[0]

def Predicate_to_filter_columns(predicate: list, column_id_mapping: dict):
    if isinstance(predicate[0], list):
        and_op = {
            "column": None,
            "operator": "AND",
            "literal": None,
            "literal_feature": None,
            "children": []
        }
        filters = []
        for sub_predicate in predicate:
            filters.append(Predicate_to_filter_columns(sub_predicate, column_id_mapping))
        and_op["children"] = filters
        return and_op
    else:
        operator = predicate[0].lower()
        if operator in logical_operator:
            logical_op = {
                "column": None,
                "operator": operator.upper(),
                "literal": None,
                "literal_feature": None,
                "children": []
            }
            for child in predicate[1]:
                logical_op["children"].append(Predicate_to_filter_columns(child, column_id_mapping))
            return logical_op
        elif operator in comparison_operator or operator in operator_mapping:
            literal_feature = 0
            if operator == "in":
                literal_feature = predicate[1][1].count(",")
            elif "like" in operator:
                literal_feature = predicate[1][1].count("%")
            if operator in operator_mapping:
                operator = operator_mapping[operator.lower()]
            if isinstance(predicate[1], list):
                if predicate[1][1][0] == "'" and predicate[1][1][-1] == "'":
                    literal = predicate[1][1][1:-1]
                else:
                    literal = predicate[1][1]
                cols = outputcol_to_id(predicate[1][0], column_id_mapping)
                if len(cols) <= 0:
                    print(f"fail to address", predicate)
                    return {}
                return {
                    "column": outputcol_to_id(predicate[1][0], column_id_mapping)[0],
                    "operator": operator,
                    "literal": literal,
                    "literal_feature": literal_feature,
                    "children": []
                }
            else:
                if predicate[2][0] == "'" and predicate[2][-1] == "'":
                    literal = predicate[2][1:-1]
                else:
                    literal = predicate[2]
                return {
                    "column": outputcol_to_id(predicate[1], column_id_mapping)[0],
                    "operator": operator,
                    "literal": literal,
                    "literal_feature": 0,
                    "children": []
                }
        else:
            raise ValueError(f"Unknown operator {operator} in predicate {predicate}")

def convert_to_zero_shot_helper(plan: dict, column_id_mapping: dict, table_id_mapping: dict, table_size_mapping):
    if plan["Name"] == "ProjectStep":
        # skip project step
        return convert_to_zero_shot_helper(plan["children"][0], column_id_mapping, table_id_mapping, table_size_mapping)
    converted_plan = {
        "plan_parameters": {
            "op_name": plan["Name"],
            "est_card": plan["EstOutputRows"],
            "est_conf": plan["EstConfidence"],
            "act_card": plan["OutputRows"],
            "output_columns": [],
            "act_children_card": 1,
            "est_children_card": 1
        },
        "children": [],
        "plan_card": plan["OutputRows"]
    }

    # parse output_columns
    output_cols = plan.get("OutputColumns", []) + plan.get("AggCalls", [])
    for output_col in output_cols:
        col_ids = outputcol_to_id(output_col, column_id_mapping)
        agg = outputcol_to_agg(output_col, aggs)
        converted_plan["plan_parameters"]["output_columns"].append({
            "aggregation": agg,
            "columns": col_ids,
        })
    
    # parse filter_columns
    # step 1 parse JoinConjucts
    join_predicates = None
    if "JoinConjuncts" in plan:
        join_predicates = JoinConjucts_to_filter_columns(plan["JoinConjuncts"], column_id_mapping)
    normal_predicates = None
    # step 2 parse predicates
    if "Predicates" in plan:
        normal_predicates = Predicate_to_filter_columns(plan["Predicates"], column_id_mapping)
        if len(normal_predicates) == 0:
            normal_predicates = None
    # merge
    if join_predicates and normal_predicates:
        converted_plan["plan_parameters"]["filter_columns"] = {
            "column": None,
            "operator": "AND",
            "literal": None,
            "literal_feature": None,
            "children": [join_predicates, normal_predicates]
        }
    elif join_predicates:
        converted_plan["plan_parameters"]["filter_columns"] = join_predicates
    elif normal_predicates:
        converted_plan["plan_parameters"]["filter_columns"] = normal_predicates

    # skip projectstep
    for child_id, child in enumerate(plan["children"]):
        if child["Name"] == "ProjectStep":
            # remove the project step
            plan["children"][child_id] = child["children"][0]
    
    # calculate children cards
    est_children_card = 1
    act_children_card = 1
    if len(plan["children"]) > 0:
        for child in plan["children"]:
            est_children_card *= child["EstOutputRows"]
            act_children_card *= child["OutputRows"]
    converted_plan["plan_parameters"]["est_children_card"] = est_children_card
    converted_plan["plan_parameters"]["act_children_card"] = act_children_card

    # add table field if a readstoragestep
    if plan["Name"] == "ReadStorageStep":
        table_name = plan["TableName"].lower()
        for table in table_id_mapping:
            if table_name.endswith(table):
                table_id = table_id_mapping[table]
                converted_plan["plan_parameters"]["table"] = table_id
                converted_plan["est_children_card"] = table_size_mapping[str(table_id)]
                converted_plan["act_children_card"] = table_size_mapping[str(table_id)]
                break

    # convert the children
    converted_children = []
    for child in plan["children"]:
        converted_children.append(convert_to_zero_shot_helper(child, column_id_mapping, table_id_mapping, table_size_mapping))
    converted_plan["children"] = converted_children

    return converted_plan

def convert_to_zero_shot(plan: dict, dataset: str):
    """schema
    plan_parameters:
        op_name: str
        est_card: float
        est_conf: float
        act_card: float
        output_columns:
            type: list
            value: 
                aggregation: str
                columns:
                    type: list
                    value: int
        act_children_card: float
        est_children_card: float
        filter_columns: # optional
            type: dict
            value: 
                column: int
                operator: str
                literal: str
                children: list
                    type: dict
        table: int # optional; only for scan
    children:
        type: list
        value: plan
    plan_card: float
    """
    if dataset == "tpch":
        from krypton_utils.tpch import col2id as column_id_mapping
        from krypton_utils.tpch import tab2id as table_id_mapping
        from krypton_utils.tpch import tab2size as table_size_mapping
    else:
        raise ValueError(f"Dataset {dataset} not supported for zero-shot conversion.")
    
    return convert_to_zero_shot_helper(plan, column_id_mapping, table_id_mapping, table_size_mapping)

    
if __name__ == "__main__":
    import json
    import sys

    plan_file = sys.argv[1]
    with open(f"{plan_file}.json") as f:
        plan = json.load(f)
    
    converted_plan = convert_to_zero_shot(plan, "tpch")
    print(json.dumps(converted_plan, indent=2))
from krypton_utils.parse_predicate import parse_predicate
from krypton_utils.parse_predicate_func import parse_predicate as parse_predicate_func
def can_skip_step(node: dict) -> bool:
    if "OutputRows" in node and "OutputRows" in node["children"][0] and \
        "Predicates" not in node and "Limit" not in node and \
        node["OutputRows"] == node["children"][0]["OutputRows"] and \
        node["Name"] in ["MergingSortedStep", "ExchangeStep", "LocalExchangeStep", "PartialSortingStep", "MergeSortingStep", "SpoolStep"]:
        return True
    elif "OutputRows" not in node:
        return True
    elif node["Name"] == "PartialAggregatingStep":
        return True
    return False


def parse_node(lines: list):
    # parse the node op line
    n_v = 0
    for i, c in enumerate(lines[0]):
        if c.isdigit():
            op_id = int(lines[0][i:].split(":")[0])
            op_name = lines[0][i:].split(":")[1].strip()
            break
        elif c == "|":
            n_v += 1
        else:
            continue

    root = {
        "Id": op_id,
        "children": [],
    }
    curr_node = root
    
    for idx, line in enumerate(lines):
        if idx == 0:
            continue

        if line.strip(" |") != "" and line.strip(" |")[0].isdigit() and "(" not in line:
            # this is a new operator line, parse it
            child = parse_node([line])
            curr_node["children"].append(child)
            curr_node = child
        elif line.strip(" |").startswith("----"):
            for idx_incre, line_1 in enumerate(lines[idx:]):
                if line_1.strip(" |") != "" and line_1.strip(" |")[0].isdigit():
                    curr_n_v = 0
                    for c in line_1:
                        if c == "|":
                            curr_n_v += 1
                        if c.isdigit():
                            break
                    if curr_n_v == n_v:
                        break
            left_child = parse_node(lines[idx + idx_incre:])
            right_child = parse_node(lines[idx: idx + idx_incre])
            curr_node["children"].append(left_child)
            curr_node["children"].append(right_child)
            break

    return root

def parse_single_predicate(predicate_str: str):
    if predicate_str[0] == "[" and predicate_str[-1] == "]":
        predicate_str = predicate_str[1:-1].strip()
    else:
        predicate_str = predicate_str.strip()
    if predicate_str[:3] == 'or(' or predicate_str[:4] == 'and(':
        return [parse_predicate_func(predicate_str)]
    else:
        predicate_str = 'and(' + predicate_str + ')'
        return [parse_predicate_func(predicate_str)]

def parse_join_conjuncts(conjuncts_str: str):
    conjunct_str_list = conjuncts_str.split(", ")
    conjuncts = []
    for conjunct_str in conjunct_str_list:
        l, op, r = conjunct_str.split(" ")
        conjuncts.append([op.strip().lower(), l.strip().lower(), r.strip().lower()])
    return conjuncts

def parse_output_schema(output_schema_str: str) -> list[str]:
    col_str_list = output_schema_str[1:-1].split(", ")
    col_list = []
    for col_str in col_str_list:
        col = col_str.split(":")[0].strip().lower()
        col_list.append(col)
    return col_list

def parse_agg_calls(agg_calls_str: str) -> list[str]:
    agg_calls_str = agg_calls_str[1:-1]
    agg_list = []
    start_pos = 0
    end_pos = 0
    depth = 0
    for i in range(len(agg_calls_str)):
        if agg_calls_str[i] == '(':
            depth += 1
        elif agg_calls_str[i] == ')':
            depth -= 1
        elif agg_calls_str[i] == ',' and depth == 0:
            end_pos = i
            agg_list.append(agg_calls_str[start_pos:end_pos].strip())
            start_pos = i + 1
        if depth == 0 and i == len(agg_calls_str) - 1:
            agg_list.append(agg_calls_str[start_pos:].strip())
    return agg_list

def parse_node_info(frag_lines) -> dict:
    node_info = {}
    last_op_id = -1
    for i, line in enumerate(frag_lines):
        if line.lstrip(" |-") != "" and line.lstrip(" |-")[0].isdigit() and "(" not in line:
            last_op_id = int(line.lstrip(" |-").split(":")[0])
            node_info[last_op_id] = {
                "Name": line.lstrip(" |-").split(":")[1].strip(),
            }
        elif last_op_id == -1:
            continue
        elif "OutputRows" in line:
            # This line contains output rows for the last operator
            if "(" in line:
                node_info[last_op_id]["OutputRows"] = int(line.split("(")[-1].split(")")[0].strip())
            else:
                node_info[last_op_id]["OutputRows"] = int(line.split(":")[-1].strip())
        elif "Est. output rows" in line and "EstOutputRows" not in node_info[last_op_id]:
            # This line contains estimated output rows for the last operator
            node_info[last_op_id]["EstOutputRows"] = int(line.split(":")[-1].strip())
        elif "Est. confidence" in line and "EstConfidence" not in node_info[last_op_id]:
            # This line contains estimated confidence for the last operator
            node_info[last_op_id]["EstConfidence"] = line.split(":")[-1].strip()
        elif "join op" in line:
            # This line contains join op info for the last operator
            node_info[last_op_id]["JoinOp"] = line.split(":")[-1].strip()
        elif "equal join conjunct" in line:
            # This line contains join conjunct info for the last operator
            if "JoinConjuncts" not in node_info[last_op_id]:
                node_info[last_op_id]["JoinConjuncts"] = []
            join_construct_str = line.split(":")[-1].strip()
            join_construct = parse_join_conjuncts(join_construct_str)
            node_info[last_op_id]["JoinConjuncts"] += join_construct
        elif "other join conjunct" in line:
            if "Predicates" not in node_info[last_op_id]:
                node_info[last_op_id]["Predicates"] = []
            join_predicate = line.split(":")[-1].strip()
            parsed_predicates = parse_predicate(join_predicate)
            node_info[last_op_id]["Predicates"] = parsed_predicates
        elif "predicates" in line:
            # This line contains predicates for the last operator
            if "Predicates" not in node_info[last_op_id]:
                node_info[last_op_id]["Predicates"] = []
            predicates = []
            for line_1 in frag_lines[i+1:]:
                if "Est. output rows:" in line_1:
                    break
                predicate_str = line_1.split(":")[-1].strip()
                parsed_predicates = parse_single_predicate(predicate_str)
                predicates += parsed_predicates
            node_info[last_op_id]["Predicates"] += predicates
        elif "filter" in line:
            if "Predicates" not in node_info[last_op_id]:
                node_info[last_op_id]["Predicates"] = []
            node_info[last_op_id]["Predicates"] += [parse_single_predicate(line.split(":")[-1].strip())]
        elif "grouping keys" in line:
            node_info[last_op_id]["GroupingKeys"] = line.split(":")[-1].strip().lower()
        elif "agg calls" in line:
            node_info[last_op_id]["AggCalls"] = parse_agg_calls(line.split(":")[-1].strip().lower())
        elif "table name" in line:
            node_info[last_op_id]["TableName"] = line.split(":")[-1].strip().lower()
        elif "limit" in line:
            node_info[last_op_id]["Limit"] = int(line.split(":")[-1].strip())
        elif "output schema" in line:
            if 'OutputColumns' not in node_info[last_op_id]:
                node_info[last_op_id]["OutputColumns"] = []
            node_info[last_op_id]["OutputColumns"] = parse_output_schema(line.split("output schema:")[-1].strip())
        elif "expr list" in line:
            if 'OutputColumns' not in node_info[last_op_id]:
                node_info[last_op_id]["OutputColumns"] = []
            for line_1 in frag_lines[i+1:]:
                if not line_1.strip(' |')[0].isdigit():
                    break
                node_info[last_op_id]["OutputColumns"].append(line_1.split(":")[1].strip().lower())
    return node_info


def parse_plan_fragment(frag_lines) -> dict:
    header_lines: list[str] = []   # non-operator lines before 1st op

    for i, ln in enumerate(frag_lines):
        if ln.strip() == "" or not ln.strip()[0].isdigit():
            # non-operator line, e.g. header or summary
            header_lines.append(ln)
            continue

        root = parse_node(frag_lines[i:])
        break

    dest_id = -1
    for line in header_lines:
        if "DEST. EXCHANGE ID" in line:
            dest_id = int(line.split(":")[-1].strip())
            break

    return dest_id, root

def merge_fragments(fragments: list[dict]) -> dict:
    all_frag_ids = set(list(range(len(fragments))))
    for frag_id in reversed(range(len(fragments))):
        dest_id = fragments[frag_id]["dest_id"]
        # search through all the leave nodes of fragments[:frag_id]

        for i in range(frag_id):
            if len(fragments[i]["root"]["children"]) == 0 and fragments[i]["root"]["Id"] == dest_id:
                # found the destination node, merge it
                fragments[i]["root"] = fragments[frag_id]["root"]
                all_frag_ids.remove(frag_id)
                continue

            node_stack = [fragments[i]["root"]]
            while node_stack:
                curr_node = node_stack.pop()
                for child_id, curr_child_node in enumerate(curr_node["children"]):
                    if len(curr_child_node["children"]) == 0 and curr_child_node["Id"] == dest_id:
                        # found the destination node, merge it
                        curr_node["children"][child_id] = fragments[frag_id]["root"]
                        all_frag_ids.remove(frag_id)
                    else:
                        node_stack.append(curr_child_node)
    return fragments[0]["root"]

def copy_cols(root_node: dict):
    if root_node["children"] == []:
        return root_node

    output_cols = []
    copy_cols(root_node["children"][0])

    if "OutputColumns" in root_node["children"][0]:
        output_cols += root_node["children"][0]["OutputColumns"]    
    if "AggCalls" in root_node["children"][0]:
        output_cols += root_node["children"][0]["AggCalls"]

    if len(root_node["children"]) > 1:
        copy_cols(root_node["children"][1])
        if "OutputColumns" in root_node["children"][1]:
            output_cols += root_node["children"][1]["OutputColumns"]
        if "AggCalls" in root_node["children"][1]:
            output_cols += root_node["children"][1]["AggCalls"]

    if "OutputColumns" not in root_node and "AggCalls" not in root_node:
        root_node["OutputColumns"] = output_cols

    return root_node

def parse_plan(text: str) -> list[dict]:
    """
    Parse a verbose plan into a list of fragment dictionaries.
    """
    lines = text.splitlines()

    fragment_ids = []
    for idx, line in enumerate(lines):
        if line.strip().startswith("PLAN FRAGMENT ID"):
            fragment_ids.append(idx)

    fragments = []
    for i, frag_id in enumerate(fragment_ids):
        start_id = frag_id
        end_id = fragment_ids[i+1] if i+1 < len(fragment_ids) else -1
        dest_id, root = parse_plan_fragment(lines[start_id:end_id])
        node_info = parse_node_info(lines[start_id:end_id])

        # traverse the root tree using dfs
        all_ops = set()
        stack = [root]
        while stack:
            curr_node = stack.pop()
            # look up node info
            if curr_node["Id"] in node_info:
                curr_node.update(node_info[curr_node["Id"]])
            else:
                curr_node["Name"] = "Unknown"
            if "children" not in curr_node:
                continue
            for child in curr_node["children"]:
                stack.append(child)
            all_ops.add(curr_node["Name"])

        stack = [root]
        while stack:
            curr_node = stack.pop()
            for idx, child_node in enumerate(curr_node["children"]):
                if len(child_node["children"]) == 2:
                    continue
                elif len(child_node["children"]) == 1:
                    while can_skip_step(child_node):
                        # skip this node
                        curr_node["children"][idx] = child_node["children"][0]
                        child_node = child_node["children"][0]
                        if child_node["children"] == []:
                            break

            stack.extend(curr_node["children"])

        # skip node if its OutputRows is the same as its child
        if len(root["children"]) == 1:
            if can_skip_step(root):
                    # skip this node
                    root = root["children"][0]


        fragment = {
            "frag_id": i + 1,
            "dest_id": dest_id,
            "root": root,
            # "node_info": node_info,
        }

        fragments.append(fragment)

    return copy_cols(merge_fragments(fragments))


import json
import os
import sys

if __name__ == "__main__":
    with open(f"plan_q{sys.argv[1]}/1.out", encoding="utf-8") as f:    # put the provided plan into plan.txt
        plan_text = f.read()

    plan = parse_plan(plan_text)

    print(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True))


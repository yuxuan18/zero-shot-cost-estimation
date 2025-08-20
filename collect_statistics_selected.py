import csv
import json
import sys

dataset = sys.argv[1]

if dataset == "devmind":
    test_data = "data/devmind/devmind_test_data_selected.json"
elif dataset == "tpcds":
    test_data = "data/tpcds/tpcds_test_data_selected.json"
elif dataset == "tpch":
    test_data = "data/tpch/test_data_selected.json"

acr_card = []
model_est_card = []
with open("results.csv") as f:
    reader = csv.reader(f)
    for row in reader:
        gt, est = row
        acr_card.append(float(gt))
        model_est_card.append(float(est))

with open(test_data) as f:
    test_data = json.load(f)["parsed_plans"]

krypton_est_card = []
for plan in test_data:
    if "est_card" in plan["plan_parameters"]:
        krypton_est_card.append(float(plan["plan_parameters"]["est_card"]))
    else:
        krypton_est_card.append(-1.0)
        # print(f"Warning: est_card not found in plan_parameters: {plan}")

# clean up
clean_acr_card = []
clean_model_est_card = []
clean_krypton_est_card = []

n_valid = 0
for gt, model_est, krypton_est in zip(acr_card, model_est_card, krypton_est_card):
    if krypton_est > 0:
        n_valid += 1
        clean_acr_card.append(gt)
        clean_model_est_card.append(model_est)
        clean_krypton_est_card.append(krypton_est)

import numpy as np
clean_acr_card = np.array(clean_acr_card)
clean_model_est_card = np.array(clean_model_est_card)
clean_krypton_est_card = np.array(clean_krypton_est_card)

model_qerror = np.maximum(clean_model_est_card / clean_acr_card, clean_acr_card / clean_model_est_card)
krypton_qerror = np.maximum(clean_krypton_est_card / clean_acr_card, clean_acr_card / clean_krypton_est_card)

with open(f"data/{dataset}/model_qerror_selected.csv", "w") as f:
    writer = csv.writer(f)
    for qerror in model_qerror:
        writer.writerow([qerror])

with open(f"data/{dataset}/krypton_qerror_selected.csv", "w") as f:
    writer = csv.writer(f)
    for qerror in krypton_qerror:
        writer.writerow([qerror])

print(f"Model Q-error: median {np.median(model_qerror):.2f}, 90th perc {np.percentile(model_qerror, 90):.2f}, 95th perc {np.percentile(model_qerror, 95):.2f}, 99th perc {np.percentile(model_qerror, 99):.2f}")
print(f"Krypton Q-error: median {np.median(krypton_qerror):.2f}, 90th perc {np.percentile(krypton_qerror, 90):.2f}, 95th perc {np.percentile(krypton_qerror, 95):.2f}, 99th perc {np.percentile(krypton_qerror, 99):.2f}")
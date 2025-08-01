import numpy as np
import scipy.stats as stats
import time

def calculate_proxy_error(training_embeddings, test_embeddings, training_labels, test_estimations, training_estimations):
    training_q_errors = np.maximum(training_labels / training_estimations, training_estimations / training_labels)

    # calculate the similarity matrix
    similarity_matrix = np.dot(test_embeddings, training_embeddings.T) / (
        np.linalg.norm(test_embeddings, axis=1, keepdims=True) * 
        np.linalg.norm(training_embeddings, axis=1, keepdims=True).T
    )
    
    # find the top-3 similar training embeddings for each test embedding
    top_indices = np.argsort(similarity_matrix, axis=1)[:, -100:]
    top_indices = np.flip(top_indices, axis=1)  # reverse to get the top 3

    # gather the labels of the top-3 similar training embeddings
    top_labels = np.log(training_q_errors[top_indices])
    top_similarities = similarity_matrix[np.arange(similarity_matrix.shape[0])[:, None], top_indices]

    # calculate the weighted mean of the top-3 labels
    mean_top_labels = np.exp(np.sum(top_labels * top_similarities, axis=1) / np.sum(top_similarities, axis=1))
    assert len(mean_top_labels) == len(test_estimations), "Length mismatch between mean labels and test estimations"

    # calculate the Q error (max(est/label, label/est)) between mean labels and test estimations
    # q_errors = np.maximum(mean_top_labels / test_estimations, test_estimations / mean_top_labels)

    return mean_top_labels

def compare(proxy_q_error, true_q_error):
    # calculate the correlation between proxy and true Q errors
    correlation, p_value = stats.pearsonr(np.log(proxy_q_error), np.log(true_q_error))
    return correlation, p_value

def calculate_bound(sample, confidence_level=0.95):
    mean = np.mean(sample)
    std_dev = np.std(sample, ddof=1)  # use sample standard deviation
    n = len(sample)
    delta = (1- confidence_level) / 2
    ub = mean + std_dev / np.sqrt(n) * np.sqrt(2 * np.log(1 / delta))
    lb = mean - std_dev / np.sqrt(n) * np.sqrt(2 * np.log(1 / delta))
    return lb, ub

def calculate_threshold_helper(proxy_q_error, true_q_error, q_error_cutoff, recall_target):
    sorted_indices = np.argsort(proxy_q_error)
    sorted_proxy_q_error = proxy_q_error[sorted_indices]
    sorted_true_q_error = true_q_error[sorted_indices]
    cumulative_recall = np.cumsum(sorted_true_q_error >= q_error_cutoff) / sum(true_q_error >= q_error_cutoff)
    threshold_index = np.searchsorted(cumulative_recall, recall_target)
    threshold = sorted_proxy_q_error[threshold_index]
    return threshold

def validate_recall(threshold, proxy_q_error, true_q_error, q_error_cutoff):
    # calculate recall
    predicted_positive = proxy_q_error >= threshold
    true_positive = true_q_error >= q_error_cutoff
    recall = np.sum(predicted_positive & true_positive) / np.sum(true_positive)
    return recall

def calculate_threshold(proxy_q_error, true_q_error, 
                        confidence_level=0.5, q_error_cutoff=100, recall_target=0.8):
    # find the maximum proxy Q error so that the recall is at least the target
    threshold = calculate_threshold_helper(proxy_q_error, true_q_error, q_error_cutoff, 1-recall_target)
    print(f"Threshold for recall {recall_target} is {threshold}")
    print(f"validated recall: {validate_recall(threshold, proxy_q_error, true_q_error, q_error_cutoff)}")
    print(f"#data above threshold: {np.sum(true_q_error >= q_error_cutoff)}")

    z1 = (proxy_q_error >= threshold) * (true_q_error >= q_error_cutoff)
    z2 = (proxy_q_error < threshold) * (true_q_error < q_error_cutoff)

    z1_lb, z1_ub = calculate_bound(z1, confidence_level)
    z2_lb, z2_ub = calculate_bound(z2, confidence_level)

    corrected_recall = z1_ub / (z1_ub + z2_lb)
    print(f"Corrected recall: {corrected_recall}")
    corrected_threshold = calculate_threshold_helper(proxy_q_error, true_q_error, q_error_cutoff, 1-corrected_recall)

    return corrected_threshold

def read_results(file_path):
    labels = []
    predictions = []
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split(',')
            assert len(parts) == 2, "Each line must contain exactly two values: label and prediction"
            label = float(parts[0])
            prediction = float(parts[1])
            labels.append(label)
            predictions.append(prediction)
    return np.array(labels), np.array(predictions)

if __name__ == "__main__":
    # set random seed for reproducibility
    np.random.seed(233)
    all_embeddings = np.load("data/tpcds/train_embeddings.npy")
    all_labels, all_predictions = read_results("data/tpcds/train_predictions.csv")
    print(f"Loaded {len(all_labels)} labels and predictions from file.")
    assert len(all_labels) == len(all_predictions), "Labels and predictions must have the same length"
    assert all_embeddings.shape[0] == len(all_labels), "Embeddings must match the number of labels"
    print(f"Loaded embeddings shape: {all_embeddings.shape}")

    # split train and valid
    split_index = np.random.choice(len(all_labels), int(0.8 * len(all_labels)), replace=False)
    train_embeddings = all_embeddings[split_index]
    train_labels = all_labels[split_index]
    train_predictions = all_predictions[split_index]
    valid_embeddings = all_embeddings[~np.isin(np.arange(len(all_labels)), split_index)]
    valid_labels = all_labels[~np.isin(np.arange(len(all_labels)), split_index)]
    valid_predictions = all_predictions[~np.isin(np.arange(len(all_labels)), split_index)]
    proxy_q_error = calculate_proxy_error(train_embeddings, valid_embeddings, train_labels, valid_predictions, train_predictions)
    print(f"mean proxy Q error: {np.mean(proxy_q_error)}")
    true_q_error = valid_labels / valid_predictions
    true_q_error = np.maximum(true_q_error, 1 / true_q_error)  # ensure Q error is >= 1
    threshold = calculate_threshold(proxy_q_error, true_q_error, 
                                    confidence_level=0.95, q_error_cutoff=25, recall_target=0.9)
    print(f"Calculated threshold: {threshold}")
    # print(f"Proxy Q error: {proxy_q_error}")
    # print(f"True Q error: {true_q_error}")
    correlation, p_value = compare(proxy_q_error, true_q_error)
    print(f"Correlation: {correlation}, p-value: {p_value}")

    eval_embeddings = np.load("data/tpcds/eval_embeddings.npy")
    eval_labels, eval_predictions = read_results("data/tpcds/eval_predictions.csv")
    start = time.time()
    proxy_q_error_eval = calculate_proxy_error(train_embeddings, eval_embeddings, train_labels, eval_predictions, train_predictions)
    end = time.time()
    count = 0
    pred_id = 0
    for proxy_q_eval, eval_pred in zip(proxy_q_error_eval, eval_predictions):
        if proxy_q_eval >= threshold:
            print(f"Prediction {pred_id}: {eval_pred} is above the threshold with proxy Q error {proxy_q_eval}")
        else:
            count += 1
        pred_id += 1
    is_below_threshold = proxy_q_error_eval < threshold

    print(f"Number of predictions below threshold: {count}")

    with open("data/tpcds/confidence.csv", "w") as f:
        for proxy_q_error, is_below in zip(proxy_q_error_eval, is_below_threshold):
            f.write(f"{proxy_q_error},{is_below}\n")

    print(f"Time taken for evaluation: {end - start} seconds")
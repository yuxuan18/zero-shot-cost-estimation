python3 krypton_preprocess.py krypton_plans/tpch --enable_subplan --query_id 3

python3 train.py \
    --gather_feature_statistics \
    --workload_runs workload_tpch.json \
    --raw_dir /users/yuxuan18/ \
    --target /users/yuxuan18/zero-shot-cost-estimation/statistics_workload_combined.json

python3 train.py \
    --train_model \
    --workload_runs ./workload_tpch.json \
    --test_workload_runs  ./workload_tpch.json \
    --statistics_file statistics_workload_combined.json \
    --target /users/yuxuan18/ \
    --hyperparameter_path setup/tuned_hyperparameters/tune_est_card_config.json \
    --max_epoch_tuples 100000 \
    --loss_class_name QLoss \
    --device cpu \
    --num_workers 16 \
    --database postgres \
    --plan_featurization KryptonEstSystemCardDetail \
    --seed 0
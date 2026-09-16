from pathlib import Path
import json
import numpy as np
from scipy.special import expit

from flybrain.reservoir import (
    Readout,
    bases_for,
    project,
    fit_logistic,
    auc,
)

RESULTS = Path("results")

DATASET_PATH = RESULTS / "flyswarm_03_fire_dataset.npz"
MODEL_PATH = RESULTS / "flyswarm_03_fire_readout.npz"
CONFIG_PATH = RESULTS / "experiment_010a_fire_threshold.json"

data = np.load(DATASET_PATH)

X = data["X"].astype(np.float32)
y = data["y"].astype(np.int64)
groups = data["groups"].astype(np.int64)

model = Readout.load(MODEL_PATH)

k = model.components
lam = model.lam

print("=" * 72)
print("EXPERIMENT 010a — OUT-OF-FOLD FIRE CALIBRATION")
print("=" * 72)

print(f"samples       : {len(y)}")
print(f"features      : {X.shape[1]}")
print(f"episodes      : {len(np.unique(groups))}")
print(f"positive rate : {y.mean()*100:.1f}%")
print(f"components    : {k}")
print(f"lambda        : {lam:g}")
print()

oof = np.full(
    len(y),
    np.nan,
    dtype=float
)

episode_aucs = []

for g in np.unique(groups):

    test = np.flatnonzero(
        groups == g
    )

    train = np.flatnonzero(
        groups != g
    )

    Xtr = X[train]
    ytr = y[train]

    Xte = X[test]
    yte = y[test]

    basis = bases_for(
        Xtr,
        [k]
    )[k]

    Ztr = project(
        basis,
        Xtr
    )

    Zte = project(
        basis,
        Xte
    )

    w, b = fit_logistic(
        Ztr,
        ytr,
        lam
    )

    p = expit(
        Zte @ w + b
    )

    oof[test] = p

    score = auc(
        yte,
        p
    )

    episode_aucs.append(
        score
    )

    print(
        f"episode {g}: "
        f"n={len(test):3d} | "
        f"hits={int(yte.sum()):2d} | "
        f"AUC={score:.3f}"
    )


# ------------------------------------------------------------
# OOF metrics
# ------------------------------------------------------------

pooled_auc = auc(
    y,
    oof
)

mean_episode_auc = float(
    np.mean(
        episode_aucs
    )
)

print()
print(
    f"Mean episode AUC : "
    f"{mean_episode_auc:.3f}"
)

print(
    f"Pooled OOF AUC   : "
    f"{pooled_auc:.3f}"
)


# ------------------------------------------------------------
# Pick threshold by balanced accuracy
# ------------------------------------------------------------

best = None

for threshold in np.linspace(
    0.05,
    0.95,
    181
):

    pred = (
        oof >= threshold
    )

    tp = int(
        np.sum(
            (pred == 1)
            & (y == 1)
        )
    )

    tn = int(
        np.sum(
            (pred == 0)
            & (y == 0)
        )
    )

    fp = int(
        np.sum(
            (pred == 1)
            & (y == 0)
        )
    )

    fn = int(
        np.sum(
            (pred == 0)
            & (y == 1)
        )
    )

    tpr = (
        tp / (tp + fn)
        if tp + fn
        else 0
    )

    tnr = (
        tn / (tn + fp)
        if tn + fp
        else 0
    )

    precision = (
        tp / (tp + fp)
        if tp + fp
        else 0
    )

    recall = tpr

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0
    )

    balanced = (
        tpr + tnr
    ) / 2

    candidate = {
        "threshold": float(
            threshold
        ),
        "balanced_accuracy": float(
            balanced
        ),
        "precision": float(
            precision
        ),
        "recall": float(
            recall
        ),
        "specificity": float(
            tnr
        ),
        "f1": float(
            f1
        ),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }

    key = (
        balanced,
        f1,
        -abs(
            threshold - 0.5
        )
    )

    if (
        best is None
        or key > best[0]
    ):
        best = (
            key,
            candidate
        )


oof_metrics = best[1]

oof_threshold = (
    oof_metrics[
        "threshold"
    ]
)

oof_fire_rate = float(
    np.mean(
        oof >= oof_threshold
    )
)


# ------------------------------------------------------------
# Full model probability scale may differ slightly from
# 3-episode OOF models.
#
# Preserve the OOF-selected decision RATE and map it to the
# full model's score distribution.
# ------------------------------------------------------------

full_prob = np.asarray(
    model.predict(X),
    dtype=float
)

deploy_threshold = float(
    np.quantile(
        full_prob,
        1.0 - oof_fire_rate
    )
)


print()
print("=" * 72)
print("OOF THRESHOLD")
print("=" * 72)

print(
    f"OOF threshold       : "
    f"{oof_threshold:.3f}"
)

print(
    f"Balanced accuracy   : "
    f"{oof_metrics['balanced_accuracy']:.3f}"
)

print(
    f"Precision           : "
    f"{oof_metrics['precision']:.3f}"
)

print(
    f"Recall              : "
    f"{oof_metrics['recall']:.3f}"
)

print(
    f"Specificity         : "
    f"{oof_metrics['specificity']:.3f}"
)

print(
    f"F1                  : "
    f"{oof_metrics['f1']:.3f}"
)

print(
    f"OOF fire fraction   : "
    f"{oof_fire_rate*100:.1f}%"
)

print()
print(
    f"DEPLOY threshold    : "
    f"{deploy_threshold:.3f}"
)


print()
print("OOF probability distribution:")

for q in [
    0.05,
    0.25,
    0.50,
    0.75,
    0.95
]:
    print(
        f"  p{int(q*100):02d}: "
        f"{np.quantile(oof, q):.3f}"
    )


config = {
    "mean_episode_auc":
        mean_episode_auc,

    "pooled_oof_auc":
        float(
            pooled_auc
        ),

    "oof_threshold":
        oof_threshold,

    "deploy_threshold":
        deploy_threshold,

    "oof_fire_rate":
        oof_fire_rate,

    **oof_metrics,
}


with open(
    CONFIG_PATH,
    "w"
) as f:

    json.dump(
        config,
        f,
        indent=2
    )


np.savez_compressed(
    RESULTS
    / "experiment_010a_oof_predictions.npz",

    y=y,
    groups=groups,
    probability=oof,
)


print()
print(
    f"Saved config: "
    f"{CONFIG_PATH}"
)

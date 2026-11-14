"""
ALVI ML - Model Evaluation & Visualization Engine (Phase 3)
Computes real classification metrics (Balanced Accuracy, Precision, Recall, Specificity,
F1, ROC-AUC) and generates evaluation figures (confusion matrices, ROC curves, feature importance).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless plotting
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def compute_classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, y_prob: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """
    Computes standard classification evaluation metrics.
    Includes specificity calculated directly from the confusion matrix.
    """
    acc = float(accuracy_score(y_true, y_pred))
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

    metrics = {
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "precision": round(prec, 4),
        "recall_sensitivity": round(rec, 4),
        "specificity": round(spec, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }

    if y_prob is not None:
        try:
            auc = float(roc_auc_score(y_true, y_prob))
            metrics["roc_auc"] = round(auc, 4)
        except Exception:
            metrics["roc_auc"] = None
    else:
        metrics["roc_auc"] = None

    return metrics


def plot_model_comparison(
    results: Dict[str, Dict[str, Any]], output_path: Path
) -> None:
    """Generates grouped bar chart comparing models on test metrics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    models = list(results.keys())
    metric_keys = ["balanced_accuracy", "f1_score", "recall_sensitivity", "specificity"]
    metric_labels = ["Balanced Acc", "F1 Score", "Recall", "Specificity"]

    x = np.arange(len(models))
    width = 0.18

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, m_key in enumerate(metric_keys):
        vals = [results[m]["test_metrics"][m_key] for m in models]
        ax.bar(x + (i - 1.5) * width, vals, width, label=metric_labels[i])

    ax.set_ylabel("Score (0.0 - 1.0)")
    ax.set_title("ALVI Baseline Models — Held-Out Test Evaluation", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontweight="semibold")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_confusion_matrix_heatmap(
    y_true: np.ndarray, y_pred: np.ndarray, model_name: str, output_path: Path
) -> None:
    """Plots formatted confusion matrix heatmap for a model."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cm = confusion_matrix(y_true, y_pred)
    classes = ["NoDementia (0)", "Dementia (1)"]

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    cax = ax.matshow(cm, cmap="Blues", alpha=0.85)

    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14, fontweight="bold")

    fig.colorbar(cax)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(classes, fontsize=10)
    ax.set_yticklabels(classes, fontsize=10)
    ax.set_xlabel("Predicted Label", fontweight="bold", labelpad=10)
    ax.set_ylabel("True Ground-Truth Label", fontweight="bold", labelpad=10)
    ax.set_title(f"Confusion Matrix: {model_name} (Test Set)", fontsize=11, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_roc_curves(
    models_dict: Dict[str, Any], X_test: np.ndarray, y_test: np.ndarray, output_path: Path
) -> None:
    """Plots ROC curves for all models with valid probability outputs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.5, 5))

    has_curves = False
    for name, model in models_dict.items():
        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_test)[:, 1]
            fpr, tpr, _ = roc_curve(y_test, y_prob)
            auc_val = roc_auc_score(y_test, y_prob)
            ax.plot(fpr, tpr, label=f"{name} (AUC = {auc_val:.3f})", linewidth=2)
            has_curves = True

    ax.plot([0, 1], [0, 1], "k--", label="Chance Baseline (AUC = 0.50)", linewidth=1.5)
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel("False Positive Rate (1 - Specificity)", fontweight="bold")
    ax.set_ylabel("True Positive Rate (Sensitivity)", fontweight="bold")
    ax.set_title("ROC Curves — Held-Out Test Set (Grouped by Speaker)", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_feature_importance(
    best_estimator: Any, feature_names: List[str], model_name: str, output_path: Path
) -> None:
    """Extracts and plots top 15 predictive acoustic features from classifier."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    classifier = best_estimator.named_steps.get("classifier", best_estimator)

    importances = None
    if hasattr(classifier, "feature_importances_"):
        importances = classifier.feature_importances_
        title_suffix = "Feature Importances"
    elif hasattr(classifier, "coef_"):
        importances = np.abs(classifier.coef_[0])
        title_suffix = "Absolute Coefficients"

    if importances is None:
        return

    top_idx = np.argsort(importances)[::-1][:15]
    top_names = [feature_names[i] for i in top_idx]
    top_vals = [importances[i] for i in top_idx]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    y_pos = np.arange(len(top_names))
    ax.barh(y_pos, top_vals[::-1], align="center", color="teal", alpha=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top_names[::-1], fontsize=9)
    ax.set_xlabel(title_suffix, fontweight="bold")
    ax.set_title(f"Top 15 Predictive Acoustic Features ({model_name})", fontsize=11, fontweight="bold")
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


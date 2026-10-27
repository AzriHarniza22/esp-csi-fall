"""Small deterministic classifiers that can be exported to embedded C."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

ALGORITHMS = (
    "nearest-centroid",
    "logistic-regression",
    "linear-svm",
    "decision-tree",
    "random-forest",
)
FEATURE_COUNT = 16
RANDOM_SEED = 20261026


@dataclass(frozen=True)
class TreeNode:
    feature: int
    threshold: float
    left: int
    right: int
    prediction: int


@dataclass(frozen=True)
class ClassifierModel:
    algorithm: str
    labels: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    centroids: tuple[tuple[float, ...], ...] = ()
    weights: tuple[tuple[float, ...], ...] = ()
    biases: tuple[float, ...] = ()
    nodes: tuple[TreeNode, ...] = ()
    tree_roots: tuple[int, ...] = ()


def _standardize(
    rows: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], tuple[float, ...], list[list[float]]]:
    if not rows or any(len(row) != FEATURE_COUNT for row in rows):
        raise ValueError(f"Training data must contain {FEATURE_COUNT}-feature rows")
    means = [
        sum(row[index] for row in rows) / len(rows)
        for index in range(FEATURE_COUNT)
    ]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((row[index] - mean) ** 2 for row in rows) / len(rows)
        scale = math.sqrt(variance)
        scales.append(scale if scale > 1e-6 else 1.0)
    normalized = [
        [(row[index] - means[index]) / scales[index] for index in range(FEATURE_COUNT)]
        for row in rows
    ]
    return tuple(means), tuple(scales), normalized


def _majority(labels: Sequence[int], class_count: int) -> int:
    counts = [0] * class_count
    for label in labels:
        counts[label] += 1
    return max(range(class_count), key=lambda index: (counts[index], -index))


def _build_tree(
    rows: list[list[float]],
    targets: list[int],
    class_count: int,
    max_depth: int,
    min_leaf: int,
    rng: random.Random,
    max_features: int | None,
) -> tuple[list[TreeNode], int]:
    nodes: list[TreeNode] = []

    def visit(indices: list[int], depth: int) -> int:
        labels = [targets[index] for index in indices]
        prediction = _majority(labels, class_count)
        node_index = len(nodes)
        nodes.append(TreeNode(-1, 0.0, -1, -1, prediction))

        if depth >= max_depth or len(set(labels)) == 1 or len(indices) < 2 * min_leaf:
            return node_index

        feature_indices = list(range(FEATURE_COUNT))
        if max_features is not None:
            feature_indices = sorted(rng.sample(
                feature_indices, min(max_features, FEATURE_COUNT)
            ))

        best: tuple[float, int, float, list[int], list[int]] | None = None
        parent_gini = 1.0 - sum(
            (labels.count(class_index) / len(labels)) ** 2
            for class_index in range(class_count)
        )
        for feature in feature_indices:
            ordered = sorted((rows[index][feature], targets[index]) for index in indices)
            left_counts = [0] * class_count
            right_counts = [0] * class_count
            for _, label in ordered:
                right_counts[label] += 1
            for split_at in range(1, len(ordered)):
                prior_label = ordered[split_at - 1][1]
                left_counts[prior_label] += 1
                right_counts[prior_label] -= 1
                if split_at < min_leaf or len(ordered) - split_at < min_leaf:
                    continue
                left_value = ordered[split_at - 1][0]
                right_value = ordered[split_at][0]
                if left_value == right_value:
                    continue
                left_size = split_at
                right_size = len(ordered) - split_at
                left_gini = 1.0 - sum(
                    (count / left_size) ** 2 for count in left_counts
                )
                right_gini = 1.0 - sum(
                    (count / right_size) ** 2 for count in right_counts
                )
                gain = parent_gini - (
                    left_size * left_gini + right_size * right_gini
                ) / len(ordered)
                threshold = (left_value + right_value) / 2.0
                if best is None or gain > best[0]:
                    left_indices = [
                        index for index in indices if rows[index][feature] <= threshold
                    ]
                    right_indices = [
                        index for index in indices if rows[index][feature] > threshold
                    ]
                    best = (gain, feature, threshold, left_indices, right_indices)

        if best is None or best[0] <= 1e-12:
            return node_index
        _, feature, threshold, left_indices, right_indices = best
        if len(left_indices) < min_leaf or len(right_indices) < min_leaf:
            return node_index

        left_child = visit(left_indices, depth + 1)
        right_child = visit(right_indices, depth + 1)
        nodes[node_index] = TreeNode(
            feature, threshold, left_child, right_child, prediction
        )
        return node_index

    root = visit(list(range(len(rows))), 0)
    return nodes, root


def fit_classifier(
    algorithm: str,
    rows: Sequence[Sequence[float]],
    labels: Sequence[str],
    class_order: tuple[str, ...],
) -> ClassifierModel:
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    if len(rows) != len(labels) or len(rows) < 2:
        raise ValueError("Training rows and labels must have matching nontrivial lengths")
    if len(class_order) < 2 or len(set(class_order)) != len(class_order):
        raise ValueError("At least two unique output classes are required")
    label_to_index = {label: index for index, label in enumerate(class_order)}
    if any(label not in label_to_index for label in labels):
        raise ValueError("Training data contains a label outside the output classes")
    means, scales, normalized = _standardize(rows)
    targets = [label_to_index[label] for label in labels]
    class_count = len(class_order)

    if algorithm == "nearest-centroid":
        centroids = []
        for class_index in range(class_count):
            class_rows = [
                row for row, target in zip(normalized, targets)
                if target == class_index
            ]
            if not class_rows:
                raise ValueError(f"No training rows for class {class_order[class_index]!r}")
            centroids.append(tuple(
                sum(row[index] for row in class_rows) / len(class_rows)
                for index in range(FEATURE_COUNT)
            ))
        return ClassifierModel(
            algorithm, class_order, means, scales, centroids=tuple(centroids)
        )

    if algorithm in {"logistic-regression", "linear-svm"}:
        weights = [[0.0] * FEATURE_COUNT for _ in class_order]
        biases = [0.0] * class_count
        if algorithm == "logistic-regression":
            learning_rate = 0.12
            regularization = 0.001
            for _ in range(700):
                grad_w = [[0.0] * FEATURE_COUNT for _ in class_order]
                grad_b = [0.0] * class_count
                for row, target in zip(normalized, targets):
                    logits = [
                        sum(w * value for w, value in zip(weights[c], row)) + biases[c]
                        for c in range(class_count)
                    ]
                    max_logit = max(logits)
                    exps = [math.exp(value - max_logit) for value in logits]
                    total = sum(exps)
                    for class_index in range(class_count):
                        error = exps[class_index] / total - (
                            1.0 if class_index == target else 0.0
                        )
                        grad_b[class_index] += error
                        for feature, value in enumerate(row):
                            grad_w[class_index][feature] += error * value
                row_count = len(normalized)
                for class_index in range(class_count):
                    biases[class_index] -= learning_rate * grad_b[class_index] / row_count
                    for feature in range(FEATURE_COUNT):
                        gradient = grad_w[class_index][feature] / row_count
                        weights[class_index][feature] -= learning_rate * (
                            gradient + regularization * weights[class_index][feature]
                        )
        else:
            rng = random.Random(RANDOM_SEED)
            learning_rate = 0.08
            regularization = 0.002
            for epoch in range(500):
                order = list(range(len(normalized)))
                rng.shuffle(order)
                rate = learning_rate / (1.0 + epoch * 0.01)
                for sample_index in order:
                    row = normalized[sample_index]
                    target = targets[sample_index]
                    for class_index in range(class_count):
                        signed_target = 1.0 if target == class_index else -1.0
                        margin = signed_target * (
                            sum(w * value for w, value in zip(weights[class_index], row))
                            + biases[class_index]
                        )
                        for feature in range(FEATURE_COUNT):
                            weights[class_index][feature] *= 1.0 - rate * regularization
                            if margin < 1.0:
                                weights[class_index][feature] += (
                                    rate * signed_target * row[feature]
                                )
                        if margin < 1.0:
                            biases[class_index] += rate * signed_target
        return ClassifierModel(
            algorithm,
            class_order,
            means,
            scales,
            weights=tuple(tuple(row) for row in weights),
            biases=tuple(biases),
        )

    if algorithm == "decision-tree":
        nodes, root = _build_tree(
            normalized, targets, class_count, 4, 2,
            random.Random(RANDOM_SEED), None
        )
        return ClassifierModel(
            algorithm, class_order, means, scales,
            nodes=tuple(nodes), tree_roots=(root,)
        )

    rng = random.Random(RANDOM_SEED)
    all_nodes: list[TreeNode] = []
    roots = []
    for _ in range(9):
        bootstrap = [rng.randrange(len(normalized)) for _ in normalized]
        sample_rows = [normalized[index] for index in bootstrap]
        sample_targets = [targets[index] for index in bootstrap]
        nodes, root = _build_tree(
            sample_rows, sample_targets, class_count, 4, 2, rng,
            max(1, int(math.sqrt(FEATURE_COUNT)))
        )
        offset = len(all_nodes)
        roots.append(offset + root)
        all_nodes.extend(
            TreeNode(
                node.feature, node.threshold,
                node.left + offset if node.left >= 0 else -1,
                node.right + offset if node.right >= 0 else -1,
                node.prediction,
            )
            for node in nodes
        )
    return ClassifierModel(
        algorithm, class_order, means, scales,
        nodes=tuple(all_nodes), tree_roots=tuple(roots)
    )


def predict_scores(
    model: ClassifierModel, row: Sequence[float]
) -> tuple[float, ...]:
    if len(row) != FEATURE_COUNT:
        raise ValueError(f"Prediction rows must contain {FEATURE_COUNT} features")
    normalized = [
        (row[index] - model.means[index]) / model.scales[index]
        for index in range(FEATURE_COUNT)
    ]
    if model.algorithm == "nearest-centroid":
        return tuple(
            -sum((value - center) ** 2 for value, center in zip(normalized, centroid))
            for centroid in model.centroids
        )
    if model.algorithm in {"logistic-regression", "linear-svm"}:
        return tuple(
            sum(weight * value for weight, value in zip(weights, normalized)) + bias
            for weights, bias in zip(model.weights, model.biases)
        )

    def predict_tree(root: int) -> int:
        node_index = root
        for _ in range(len(model.nodes)):
            node = model.nodes[node_index]
            if node.feature < 0:
                return node.prediction
            node_index = node.left if normalized[node.feature] <= node.threshold else node.right
        raise ValueError("Invalid tree structure")

    scores = [0.0] * len(model.labels)
    for root in model.tree_roots:
        scores[predict_tree(root)] += 1.0
    return tuple(scores)


def predict(model: ClassifierModel, row: Sequence[float]) -> str:
    scores = predict_scores(model, row)
    return model.labels[max(range(len(scores)), key=lambda index: scores[index])]

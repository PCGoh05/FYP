"""
Evaluation helper for the manuscript compliance checker.

Usage:
    python evaluate_checker.py
    python evaluate_checker.py --labels evaluation_labels.json
    python evaluate_checker.py --export-label-template evaluation_labels.json

Label schema:
{
  "files": {
    "sample.docx": {
      "paragraphs": [
        {"index": 0, "type": "journal_header"},
        {"index": 3, "type": "paper_title"}
      ],
      "issues": [
        {
          "category": "title",
          "location": "Paper Title",
          "description": "Title font size does not match template"
        }
      ]
    }
  }
}
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from modules.manuscript_checker import ManuscriptChecker
from modules.template_extractor import TemplateExtractor


IssueKey = Tuple[str, str, str]
ParagraphKey = Tuple[int, str]
FileIssueKey = Tuple[str, str, str, str]
FileParagraphKey = Tuple[str, int, str]


def normalize_text(value: object) -> str:
    """Normalize text for stable metric comparisons."""
    return str(value or "").strip().lower()


def issue_to_key(issue) -> IssueKey:
    """Convert an issue object to a stable comparison key."""
    return (
        normalize_text(issue.category),
        normalize_text(issue.location),
        normalize_text(issue.description),
    )


def label_to_issue_key(label: Dict) -> IssueKey:
    """Convert a manual issue label to a stable comparison key."""
    return (
        normalize_text(label.get("category")),
        normalize_text(label.get("location")),
        normalize_text(label.get("description")),
    )


def classification_to_key(classification) -> ParagraphKey:
    """Convert a paragraph classification to a stable comparison key."""
    return (
        int(classification.index),
        normalize_text(classification.paragraph_type.value),
    )


def label_to_paragraph_key(label: Dict) -> Optional[ParagraphKey]:
    """Convert a manual paragraph label to a stable comparison key."""
    if "index" not in label or "type" not in label:
        return None
    return (
        int(label["index"]),
        normalize_text(label["type"]),
    )


def load_rules(template_path: Path) -> Dict:
    """Extract deterministic rules from the template."""
    extractor = TemplateExtractor()
    extractor.load(str(template_path), template_name=template_path.name)
    return extractor.extract_all_rules()


def run_checker(rules: Dict, manuscript_path: Path):
    """Run all checks for one manuscript."""
    checker = ManuscriptChecker(rules)
    checker.load_manuscript(str(manuscript_path))
    return checker.check_all()


def is_word_temp_file(path: Path) -> bool:
    """Return True for Word temporary lock files."""
    return path.name.startswith("~$")


def discover_sample_files(samples_dir: Path, template_path: Path) -> List[Path]:
    """Find usable DOCX sample files and skip templates or Word temp files."""
    template_name = template_path.name.lower()
    files = []

    for path in sorted(samples_dir.glob("*.docx")):
        if not path.is_file():
            continue
        if is_word_temp_file(path):
            print(f"Skipping Word temporary file: {path.name}")
            continue
        path_name = path.name.lower()
        if path_name == template_name or "template" in path_name:
            print(f"Skipping template file: {path.name}")
            continue
        files.append(path)

    return files


def flatten_detected_issues(result) -> Set[IssueKey]:
    """Flatten checker issues into comparable keys."""
    keys = set()
    for issues in result.issues_by_category.values():
        for issue in issues:
            keys.add(issue_to_key(issue))
    return keys


def flatten_label_issues(labels: Iterable[Dict]) -> Set[IssueKey]:
    """Flatten manual issue labels into comparable keys."""
    return {label_to_issue_key(label) for label in labels}


def flatten_detected_paragraphs(result) -> Set[ParagraphKey]:
    """Flatten detected paragraph classifications into comparable keys."""
    return {classification_to_key(classification) for classification in result.classifications}


def flatten_label_paragraphs(labels: Iterable[Dict]) -> Set[ParagraphKey]:
    """Flatten manual paragraph labels into comparable keys."""
    keys = set()
    for label in labels:
        key = label_to_paragraph_key(label)
        if key is not None:
            keys.add(key)
    return keys


def calculate_set_metrics(predicted: Set[Tuple], expected: Set[Tuple]) -> Dict[str, float]:
    """Calculate precision, recall, and F1-score for set comparisons."""
    true_positive = len(predicted & expected)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def calculate_classification_metrics(predicted_by_index: Dict[int, str], expected_by_index: Dict[int, str]) -> Dict[str, float]:
    """Calculate paragraph classification accuracy, precision, recall, and F1-score."""
    predicted = {
        (index, predicted_by_index[index])
        for index in expected_by_index
        if index in predicted_by_index
    }
    expected = {(index, paragraph_type) for index, paragraph_type in expected_by_index.items()}
    metrics = calculate_set_metrics(predicted, expected)

    comparable_indexes = set(expected_by_index)
    correct = sum(
        1
        for index in comparable_indexes
        if predicted_by_index.get(index) == expected_by_index[index]
    )
    accuracy = correct / len(comparable_indexes) if comparable_indexes else 0.0
    metrics["accuracy"] = round(accuracy, 4)
    metrics["labelled_paragraphs"] = len(comparable_indexes)
    return metrics


def build_confusion_matrix(predicted_by_key: Dict[Tuple, str], expected_by_key: Dict[Tuple, str]) -> Dict[str, Dict[str, int]]:
    """Build a simple expected-by-predicted confusion matrix."""
    matrix: Dict[str, Counter] = defaultdict(Counter)
    for key, expected_type in expected_by_key.items():
        predicted_type = predicted_by_key.get(key, "missing")
        matrix[expected_type][predicted_type] += 1

    return {
        expected_type: dict(sorted(predicted_counts.items()))
        for expected_type, predicted_counts in sorted(matrix.items())
    }


def print_smoke_summary(file_name: str, result) -> None:
    """Print a compact summary for one manuscript."""
    categories = {
        category: len(issues)
        for category, issues in result.issues_by_category.items()
        if issues
    }
    paragraph_counts = result.statistics.get("paragraph_types", {})
    first_items = [
        (cp.index, cp.paragraph_type.value, cp.text[:55])
        for cp in result.classifications
        if cp.text
    ][:10]

    print(f"\nFILE: {file_name}")
    print(f"Score: {result.compliance_score}%")
    print(f"Issues: {result.total_issues}")
    print(f"Issue categories: {categories}")
    print(f"Paragraph classifications: {paragraph_counts}")
    print(f"Structure: {result.document_structure}")
    print("First classified paragraphs:")
    for index, paragraph_type, preview in first_items:
        print(f"  [{index:03d}] {paragraph_type:18s} {preview}")


def result_to_label_entry(result) -> Dict:
    """Create a starter manual-label entry from current checker output."""
    paragraphs = [
        {
            "index": classification.index,
            "type": classification.paragraph_type.value,
        }
        for classification in result.classifications
        if classification.text
    ]

    issues = [
        {
            "category": issue.category,
            "location": issue.location,
            "description": issue.description,
        }
        for issues_by_category in result.issues_by_category.values()
        for issue in issues_by_category
    ]

    return {
        "paragraphs": paragraphs,
        "issues": issues,
    }


def export_label_template(output_path: Path, rules: Dict, sample_files: List[Path]) -> None:
    """Export a starter label file for manual correction."""
    label_data = {
        "files": {}
    }

    for manuscript_path in sample_files:
        try:
            result = run_checker(rules, manuscript_path)
        except Exception as error:
            print(f"Skipping invalid sample during label export: {manuscript_path.name} ({error})")
            continue
        label_data["files"][manuscript_path.name] = result_to_label_entry(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(label_data, output_file, indent=2, ensure_ascii=False)

    print(f"Label template exported: {output_path}")


def load_labels(labels_path: Optional[str]) -> Dict:
    """Load manual labels if a labels path is provided."""
    if not labels_path:
        return {}
    with open(labels_path, "r", encoding="utf-8-sig") as label_file:
        return json.load(label_file).get("files", {})


def print_file_metrics(file_name: str, result, file_labels: Dict) -> Tuple[Set[IssueKey], Set[IssueKey], Dict[int, str], Dict[int, str]]:
    """Print per-file metrics and return normalized metric inputs."""
    predicted_issues = flatten_detected_issues(result)
    expected_issues = flatten_label_issues(file_labels.get("issues", []))

    predicted_paragraphs = {
        classification.index: classification.paragraph_type.value
        for classification in result.classifications
    }
    expected_paragraphs = {
        index: paragraph_type
        for index, paragraph_type in flatten_label_paragraphs(file_labels.get("paragraphs", []))
    }

    if expected_issues:
        issue_metrics = calculate_set_metrics(predicted_issues, expected_issues)
        print(f"Issue metrics for {file_name}: {json.dumps(issue_metrics, sort_keys=True)}")

    if expected_paragraphs:
        classification_metrics = calculate_classification_metrics(predicted_paragraphs, expected_paragraphs)
        print(f"Paragraph metrics for {file_name}: {json.dumps(classification_metrics, sort_keys=True)}")

    return predicted_issues, expected_issues, predicted_paragraphs, expected_paragraphs


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the manuscript checker.")
    parser.add_argument("--template", default="samples/JIWE_Template.docx")
    parser.add_argument("--samples", default="samples")
    parser.add_argument("--labels", default=None)
    parser.add_argument("--export-label-template", default=None)
    args = parser.parse_args()

    template_path = Path(args.template)
    samples_dir = Path(args.samples)
    rules = load_rules(template_path)
    sample_files = discover_sample_files(samples_dir, template_path)

    if args.export_label_template:
        export_label_template(Path(args.export_label_template), rules, sample_files)
        return

    labels_data = load_labels(args.labels)

    all_predicted_issues: Set[FileIssueKey] = set()
    all_expected_issues: Set[FileIssueKey] = set()
    all_predicted_paragraphs: Dict[Tuple[str, int], str] = {}
    all_expected_paragraphs: Dict[Tuple[str, int], str] = {}
    skipped_invalid = []

    for manuscript_path in sample_files:
        try:
            result = run_checker(rules, manuscript_path)
        except Exception as error:
            skipped_invalid.append(manuscript_path.name)
            print(f"\nSkipping invalid sample: {manuscript_path.name}")
            print(f"Reason: {error}")
            continue

        print_smoke_summary(manuscript_path.name, result)

        file_labels = labels_data.get(manuscript_path.name, {})
        predicted_issues, expected_issues, predicted_paragraphs, expected_paragraphs = print_file_metrics(
            manuscript_path.name,
            result,
            file_labels,
        )

        all_predicted_issues.update({(manuscript_path.name, *key) for key in predicted_issues})
        all_expected_issues.update({(manuscript_path.name, *key) for key in expected_issues})

        for index, paragraph_type in predicted_paragraphs.items():
            all_predicted_paragraphs[(manuscript_path.name, index)] = paragraph_type
        for index, paragraph_type in expected_paragraphs.items():
            all_expected_paragraphs[(manuscript_path.name, index)] = paragraph_type

    if labels_data:
        paragraph_predicted_set: Set[FileParagraphKey] = {
            (file_name, index, all_predicted_paragraphs[(file_name, index)])
            for file_name, index in all_expected_paragraphs
            if (file_name, index) in all_predicted_paragraphs
        }
        paragraph_expected_set: Set[FileParagraphKey] = {
            (file_name, index, paragraph_type)
            for (file_name, index), paragraph_type in all_expected_paragraphs.items()
        }
        paragraph_metrics = calculate_set_metrics(paragraph_predicted_set, paragraph_expected_set)

        comparable_paragraphs = len(all_expected_paragraphs)
        correct_paragraphs = sum(
            1
            for key, expected_type in all_expected_paragraphs.items()
            if all_predicted_paragraphs.get(key) == expected_type
        )
        paragraph_metrics["accuracy"] = round(
            correct_paragraphs / comparable_paragraphs,
            4,
        ) if comparable_paragraphs else 0.0
        paragraph_metrics["labelled_paragraphs"] = comparable_paragraphs

        confusion_matrix = build_confusion_matrix(all_predicted_paragraphs, all_expected_paragraphs)

        print("\nOVERALL ISSUE METRICS")
        print(json.dumps(calculate_set_metrics(all_predicted_issues, all_expected_issues), indent=2, sort_keys=True))
        print("\nOVERALL PARAGRAPH CLASSIFICATION METRICS")
        print(json.dumps(paragraph_metrics, indent=2, sort_keys=True))
        print("\nPARAGRAPH CONFUSION MATRIX")
        print(json.dumps(confusion_matrix, indent=2, sort_keys=True))
    else:
        print("\nNo manual labels provided. Smoke test completed.")
        print("Add --labels evaluation_labels.json to calculate precision, recall, and F1-score.")
        print("Use --export-label-template evaluation_labels.json to create a starter label file.")

    if skipped_invalid:
        print(f"\nInvalid samples skipped: {', '.join(skipped_invalid)}")


if __name__ == "__main__":
    main()

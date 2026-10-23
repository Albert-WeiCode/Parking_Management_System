"""Evaluate the local pipeline against held-out CLPD images, without training."""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from recognize.service import recognize_plate


def evaluate(limit):
    with (ROOT / 'CLPD/CLPD.csv').open(encoding='gbk', newline='') as handle:
        labels = {Path(row['path']).name: row['label'] for row in csv.DictReader(handle)}
    images = sorted((ROOT / 'dataset/images/test').glob('*.jpg'), key=lambda p: int(p.stem))[:limit]
    rows = []
    for path in images:
        predictions = recognize_plate(path)
        expected = labels[path.name]
        rows.append({'image': path.name, 'expected': expected,
                     'predictions': predictions,
                     'exact_match': any(item['plate_number'] == expected for item in predictions)})
    return {'samples': len(rows), 'exact_matches': sum(row['exact_match'] for row in rows), 'results': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=30)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error('--limit must be positive')
    report = evaluate(args.limit)
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Exact matches: {report['exact_matches']}/{report['samples']}")

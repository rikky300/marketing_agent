"""採点モデル(BERT)をコマンドだけでローカル学習する。Colab(post_evaluator.ipynb)不要。

学習データ: notebooks/labels.jsonl（無ければ先に python notebooks/gen_labels.py で作る）
出力先: config.LOCAL_MODEL_DIR（既定 local/models/post_evaluator/）

実行:
    python notebooks/train_evaluator.py
    python notebooks/train_evaluator.py --epochs 5 --out local/models/post_evaluator

post_evaluator.ipynb と同じモデル構成・損失・ハイパーパラメータ。GPUがあれば自動で使う。
"""
import argparse
import json
import os
import sys

# notebooks/ から `python notebooks/train_evaluator.py` で直接実行できるよう、
# リポジトリ直下(config.py・scoring/がある場所)をsys.pathに足す。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer

import config
from scoring.local_evaluator import PostEvaluatorModel

LABELS_FILE = os.path.join(os.path.dirname(__file__), "labels.jsonl")
MAX_LEN = 128
BATCH_SIZE = 8


def _norm(v):
    """1〜5 を 0〜1 に正規化（回帰ヘッドがsigmoidで0〜1を出すため）。"""
    return torch.tensor((v - 1) / 4, dtype=torch.float)


class PostDataset(Dataset):
    def __init__(self, records, tokenizer):
        self.records = records
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        r = self.records[idx]
        enc = self.tokenizer(r["text"], max_length=MAX_LEN, padding="max_length",
                             truncation=True, return_tensors="pt")
        return {
            "input_ids": enc["input_ids"].squeeze(),
            "attention_mask": enc["attention_mask"].squeeze(),
            "hook": _norm(r["hook"]),
            "specificity": _norm(r["specificity"]),
            "clarity": _norm(r["clarity"]),
            "relatability": _norm(r["relatability"]),
            "binary": torch.tensor(r["binary"], dtype=torch.long),
        }


def run_epoch(model, loader, device, mse, ce, optimizer=None):
    is_train = optimizer is not None
    model.train(is_train)
    total_loss = 0.0
    for batch in loader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        with torch.set_grad_enabled(is_train):
            hook, spec, clar, rel, binary_logits = model(input_ids, attention_mask)
            loss = (
                mse(hook, batch["hook"].to(device)) * 2.0
              + mse(spec, batch["specificity"].to(device)) * 2.0
              + mse(clar, batch["clarity"].to(device)) * 2.0
              + mse(rel, batch["relatability"].to(device)) * 2.0
              + ce(binary_logits, batch["binary"].to(device)) * 1.0
            )
        if is_train:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default=LABELS_FILE, help="学習データ(JSONL)")
    parser.add_argument("--out", default=config.LOCAL_MODEL_DIR, help="モデルの保存先")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    with open(args.labels, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    print(f"学習データ: {len(records)}件 ({args.labels})")

    train_records, val_records = train_test_split(
        records, test_size=0.2, random_state=42,
        stratify=[r["binary"] for r in records])
    print(f"訓練 {len(train_records)}件 / 検証 {len(val_records)}件")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用デバイス: {device}")

    tokenizer = AutoTokenizer.from_pretrained(config.BERT_MODEL)
    bert = AutoModel.from_pretrained(config.BERT_MODEL)
    model = PostEvaluatorModel(bert).to(device)

    train_loader = DataLoader(PostDataset(train_records, tokenizer), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(PostDataset(val_records, tokenizer), batch_size=BATCH_SIZE, shuffle=False)

    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    mse, ce = nn.MSELoss(), nn.CrossEntropyLoss()

    best_val_loss = float("inf")
    best_state = None
    print(f"{'Epoch':>6} {'Train Loss':>12} {'Val Loss':>10}")
    print("-" * 32)
    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(model, train_loader, device, mse, ce, optimizer)
        val_loss = run_epoch(model, val_loader, device, mse, ce)
        marker = " ← best" if val_loss < best_val_loss else ""
        print(f"{epoch:>6} {train_loss:>12.4f} {val_loss:>10.4f}{marker}")
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    print(f"\n学習完了。最良の検証損失: {best_val_loss:.4f}")

    os.makedirs(args.out, exist_ok=True)
    torch.save(best_state, os.path.join(args.out, "pytorch_model.pt"))
    tokenizer.save_pretrained(args.out)
    meta = {
        "base_model": config.BERT_MODEL,
        "max_len": MAX_LEN,
        "score_min": 1,
        "score_max": 5,
        "axes": ["hook", "specificity", "clarity", "relatability"],
        "best_val_loss": best_val_loss,
        "train_size": len(train_records),
        "val_size": len(val_records),
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"保存しました: {args.out}/")
    for fname in os.listdir(args.out):
        size = os.path.getsize(os.path.join(args.out, fname)) / 1024 / 1024
        print(f"  {fname}: {size:.1f} MB")


if __name__ == "__main__":
    main()

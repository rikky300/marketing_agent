"""自前採点モデル（BERT ファインチューニング）のローカル推論。

CLAUDE.md §7.2 の構成に合わせた実装:
  投稿テキスト → BERT(cl-tohoku/bert-base-japanese-v3) → [CLS] →
    hook_head / specificity_head (sigmoid 0〜1、表示は1〜5) + binary_head (good/bad)

nodes._evaluate が get_evaluator().score() を呼ぶ（採点はこのモデルのみ。LLMはジャッジに使わない）。
torch/transformers はここでしか import しない。

⚠ 実際の学習ノートブックの保存形式に合わせて、下の「reconcile」箇所を確認すること:
  - 重みファイル名と state_dict のキー（モデル全体の state_dict を想定）
  - meta.json のスキーマ（max_len / スコアの min-max）
  - tokenizer が model_dir に save_pretrained されていること
  cl-tohoku/bert-base-japanese-v3 のトークナイザは fugashi + unidic_lite が必要。
"""
import json
import os

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoTokenizer

import config

# 重みファイルの候補（先に見つかったものを使う）。notebookは pytorch_model.pt で保存する
_WEIGHT_NAMES = ["pytorch_model.pt", "pytorch_model.bin", "model.pt", "best_model.pt"]


class PostEvaluatorModel(nn.Module):
    """BERT + 5ヘッド。notebookの PostEvaluator と属性名を一致させる（state_dictのキーになる）。
    dropout/sigmoid はパラメータを持たないので推論(eval)では省略しても結果は同じ。"""

    def __init__(self, bert):
        super().__init__()
        self.bert = bert
        hidden = bert.config.hidden_size  # 768
        self.hook_head = nn.Linear(hidden, 1)
        self.specificity_head = nn.Linear(hidden, 1)
        self.clarity_head = nn.Linear(hidden, 1)
        self.relatability_head = nn.Linear(hidden, 1)
        self.binary_head = nn.Linear(hidden, 2)

    def forward(self, input_ids, attention_mask):
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0, :]  # [CLS] トークン
        hook = torch.sigmoid(self.hook_head(cls)).squeeze(-1)                # 0〜1
        specificity = torch.sigmoid(self.specificity_head(cls)).squeeze(-1)  # 0〜1
        clarity = torch.sigmoid(self.clarity_head(cls)).squeeze(-1)          # 0〜1
        relatability = torch.sigmoid(self.relatability_head(cls)).squeeze(-1)  # 0〜1
        binary_logits = self.binary_head(cls)                                # (N,2)
        return hook, specificity, clarity, relatability, binary_logits


def _find_weights(model_dir):
    for name in _WEIGHT_NAMES:
        p = os.path.join(model_dir, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        f"{model_dir} に重みファイルが見つかりません（候補: {_WEIGHT_NAMES}）。"
        " models/post_evaluator/ にモデルを配置してください。")


class LocalEvaluator:
    """遅延ロードのシングルトンとして使う。初回 score() 呼び出し時にモデルを読み込む。"""

    def __init__(self, model_dir=None):
        self.model_dir = model_dir or config.LOCAL_MODEL_DIR
        self._model = None
        self._tokenizer = None
        self._meta = {}

    def _load(self):
        if self._model is not None:
            return
        if not os.path.isdir(self.model_dir):
            raise FileNotFoundError(f"モデルディレクトリが無い: {self.model_dir}")
        print(f"[モデル] 自前モデルを読み込み中: {self.model_dir}/ (初回のみ)")

        # meta.json（無くてもデフォルトで動く）。⚠ notebookの保存内容に合わせる
        meta_path = os.path.join(self.model_dir, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                self._meta = json.load(f)
        self._max_len = int(self._meta.get("max_len", 128))
        self._smin = float(self._meta.get("score_min", 1))
        self._smax = float(self._meta.get("score_max", 5))

        # トークナイザ（model_dir に save_pretrained 済みを想定。無ければベースモデルから）
        tok_src = self.model_dir if os.path.exists(
            os.path.join(self.model_dir, "tokenizer_config.json")) else config.BERT_MODEL
        self._tokenizer = AutoTokenizer.from_pretrained(tok_src)

        # BERT本体は state_dict に全部入っている想定なので config から空で組み、あとで load。
        cfg_src = self.model_dir if os.path.exists(
            os.path.join(self.model_dir, "config.json")) else config.BERT_MODEL
        bert = AutoModel.from_config(AutoConfig.from_pretrained(cfg_src))
        model = PostEvaluatorModel(bert)

        state = torch.load(_find_weights(self.model_dir), map_location="cpu")
        if isinstance(state, dict) and "state_dict" in state:  # チェックポイント形式なら中を取る
            state = state["state_dict"]
        model.load_state_dict(state)  # ⚠ キー不一致ならnotebookのクラス定義に合わせる
        model.eval()
        self._model = model
        n_params = sum(p.numel() for p in model.parameters())
        print(f"[モデル] 読み込み完了 (params={n_params:,} / max_len={self._max_len} / CPU)")

    def _to_1_5(self, x):
        """sigmoid(0〜1) を 表示スコア(1〜5) に。notebookの predict と同じく int() で切り捨て→クランプ。"""
        v = int(self._smin + float(x) * (self._smax - self._smin))
        return int(max(self._smin, min(self._smax, v)))

    @torch.no_grad()
    def score(self, text):
        """4軸(1〜5) + binary(0/1) を dict で返す。
        {"hook","specificity","clarity","relatability","binary"}"""
        self._load()
        enc = self._tokenizer(text, truncation=True, max_length=self._max_len,
                              padding="max_length", return_tensors="pt")
        hook, spec, clar, rel, binary_logits = self._model(enc["input_ids"], enc["attention_mask"])
        return {
            "hook": self._to_1_5(hook[0]),
            "specificity": self._to_1_5(spec[0]),
            "clarity": self._to_1_5(clar[0]),
            "relatability": self._to_1_5(rel[0]),
            "binary": int(torch.argmax(binary_logits, dim=-1)[0]),
        }


_singleton = None


def get_evaluator():
    """プロセス内で1回だけモデルを読み込むためのシングルトン。"""
    global _singleton
    if _singleton is None:
        _singleton = LocalEvaluator()
    return _singleton

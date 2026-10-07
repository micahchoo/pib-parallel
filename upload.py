# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["huggingface_hub"]
# ///
"""One month, or one regional language, to the Hugging Face dataset, with the card, in one commit.

    uv run upload.py data 2019-07        sentences/2019-07.parquet, documents/2019-07.parquet, README.md
    uv run upload.py data regional/ne    regional/sentences/ne.parquet, regional/documents/ne.parquet, README.md

Files of the first, single-month layout (sentences.parquet at the top) are removed in the same commit.
"""
import pathlib
import sys

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

REPO = "micahchoo/pib-parallel"
data, month = pathlib.Path(sys.argv[1]), sys.argv[2]
api = HfApi()
present = set(api.list_repo_files(REPO, repo_type="dataset"))
if month.startswith("regional/"):
    lang = month.split("/", 1)[1]
    target = lambda name: f"regional/{name}/{lang}.parquet"
else:
    target = lambda name: f"{name}/{month}.parquet"
ops = [CommitOperationAdd(target(name), str(data / month / "release" / f"{name}.parquet")) for name in ("sentences", "documents")]
ops.append(CommitOperationAdd("README.md", str(data / "hf" / "README.md")))
ops += [CommitOperationDelete(old) for old in ("sentences.parquet", "documents.parquet") if old in present]
commit = api.create_commit(REPO, repo_type="dataset", operations=ops, commit_message=f"{month}, and the card for every month")
print(commit.commit_url)

# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["huggingface_hub"]
# ///
"""One month to the Hugging Face dataset, with the card rebuilt for every month, in one commit.

    uv run upload.py data 2019-07        sentences/2019-07.parquet, documents/2019-07.parquet, README.md

Files of the first, single-month layout (sentences.parquet at the top) are removed in the same commit.
"""
import pathlib
import sys

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

REPO = "micahchoo/pib-parallel"
data, month = pathlib.Path(sys.argv[1]), sys.argv[2]
api = HfApi()
present = set(api.list_repo_files(REPO, repo_type="dataset"))
ops = [CommitOperationAdd(f"{name}/{month}.parquet", str(data / month / "release" / f"{name}.parquet")) for name in ("sentences", "documents")]
ops.append(CommitOperationAdd("README.md", str(data / "hf" / "README.md")))
ops += [CommitOperationDelete(old) for old in ("sentences.parquet", "documents.parquet") if old in present]
commit = api.create_commit(REPO, repo_type="dataset", operations=ops, commit_message=f"{month}, and the card for every month")
print(commit.commit_url)

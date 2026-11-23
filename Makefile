.PHONY: check eval

# Offline recomputation of the README table.
# Does not call DeepSeek, Semantic Scholar, or Crossref.
check:
	python3 -c "import docx, dotenv" >/dev/null 2>&1 || python3 -m pip install -q -r requirements-check.txt
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python3 check_claims.py

eval: check

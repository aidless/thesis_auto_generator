# Contributing

Thanks for your interest in improving this repository.

## Getting set up

```bash
git clone https://github.com/aidless/thesis_auto_generator.git
cd thesis_auto_generator
pip install -r requirements.txt   # if present
```

## Verifying your change

```bash
python3 -m pip install -r requirements-check.txt
make check
```

`make check` reruns the unit tests and recomputes the README table. It does not
call DeepSeek, Semantic Scholar, or Crossref, and it does not need an API key.
`check_env.py` is a separate diagnostic; it is not this result.

## Pull requests

- One logical change per pull request.
- Explain what breaks or is missing without the change.
- State how you verified it, and paste the command output.
- Keep unrelated reformatting out of the diff.

## Security

Do not open a public issue for a security problem. Use the private channel described
in [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

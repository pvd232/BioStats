# Development environment

VIPER repository commands use the Conda environment named `mantra`.

Use the Conda environment named `mantra` for repository Python, package, test,
schema, and validation commands.

```bash
conda activate mantra
```

Confirm the environment once after activation:

```bash
echo "$CONDA_DEFAULT_ENV"
python -c 'import sys; print(sys.executable)'
```

The environment name must be `mantra`, and Python must resolve from that Conda
environment before repository Python commands run.
